import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import GameData, Discounts, TeamData, Stats
from Utils.request_caller import SportbookRequestType
from Redis.redis_manager import RedisAsyncManager
from datetime import datetime

class Ownerbox(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="ownerbox", request_type=SportbookRequestType.ASYNC)
        self.LEAGUES = [
            "MLB", "NFL", "PGA", "NBA", "NHL"
        ]

    async def get_game_data(self, session: aiohttp.ClientSession, headers: dict, league: str) -> list:
        stats = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("stat_url").format(league=league),
            method=self.book_data.method,
            headers=headers
        )

        if not stats:
            return []

        valid_stats = {
            stat.get("id"): stat.get("sport")
            for stat in stats
        }

        if not valid_stats:
            return []

        tasks = [
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("game_url").format(market_id=stat, league=league),
                method=self.book_data.method,
                headers=headers
            )

            for stat, league in valid_stats.items()
        ]

        return await asyncio.gather(*tasks)

    def _extract_game_data(self, game_data: dict) -> GameData:
        team_a = game_data.get("game", {}).get("homeTeam", {}).get("alias")
        team_b = game_data.get("game", {}).get("awayTeam", {}).get("alias")
        player_team = game_data.get("player", {}).get("teamAlias")
        player_name = f"{game_data.get('player').get('firstName')} {game_data.get('player').get('lastName')}"
        start_date = datetime.fromtimestamp(game_data.get("game").get("date") / 1000).isoformat()

        if team_a and team_b:
            team_key = Ownerbox.generate_key([team_a, team_b, start_date])
        else:
            team_key = Ownerbox.generate_key([player_name, start_date])

        options = ["over", "under"] if game_data.get("pickOptions") == "MORE_OR_LESS" else ["over"]
        discounts = Discounts(
            discount_name="Discount",
            discount_percentage=game_data.get("discount", {}).get("discountPercentage"),
            discount_expiry=datetime.fromtimestamp(game_data.get("discount", {}).get("expiry") / 1000).isoformat()
        ) if game_data.get("isDiscounted") else {}

        return GameData(
            league=game_data.get("sport").lower(),
            game_key=team_key,
            start_date=start_date,
            team_data=TeamData(
                team_a=team_a,
                team_b=team_b,
            ),
            future=False,
            odds=[
                Stats(
                    player_name=player_name,
                    player_team=player_team,
                    stat_type=game_data.get("marketType").get("name").lower(),
                    line=game_data.get("line").get("balancedLine") if not game_data.get(
                        "isDiscounted") else game_data.get("discount").get("discountLine"),
                    bet_type=option,
                    regular_line=not game_data.get("isDiscounted"),
                    discounts=discounts
                )

                for option in options
            ],
            solo_game=False if all([team_a, team_b]) else True
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            redis_instance = RedisAsyncManager(database=5)
            auth_token = await redis_instance.get_data("ownerbox_auth_token")

            if not auth_token:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="auth_failure",
                    message="Couldn't retrieve Ownerbox access token from Redis.",
                    level="error"
                )
                return

            headers = {
                **self.book_data.headers,
                'Cookie': f'obauth={auth_token}'
            }

            tasks = [
                self.get_game_data(
                    session=session,
                    headers=headers,
                    league=league
                )
                for league in self.LEAGUES
            ]

            game_data = await asyncio.gather(*tasks)

            merged_data = [
                game for response in game_data
                if response
                for sublist in response
                if sublist
                for game in sublist.get("data", [])
                if game
            ]

            if not merged_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No game data returned",
                    level="error"
                )
                return

            events = {}
            for game_details in merged_data:
                player_data = self._extract_game_data(game_details)
                if player_data:
                    self.add_to_events(events, player_data, GameData)

            ownerbox_data = list(events.values())

            mapped_data = await self.external_mapper(ownerbox_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data