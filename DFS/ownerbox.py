from datetime import datetime
import aiohttp
import asyncio
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Mapper.static_mapper import STAT_TYPES, LEAGUES
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, Discounts

#### HAVE TO GET ALL MARKET_TYPES OR ALL PLAYERS WON'T SHOW UP ####

class Ownerbox(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="ownerbox")
        self.LEAGUES = [
            "MLB", "NFL", "PGA", "NBA", "NHL"
        ]
        self.redis = RedisManager(db=5)

    async def get_game_data(self, session: aiohttp.ClientSession, headers: dict, league: str):
        stats = await self.api_caller(
            session=session,
            url=self.book_data.url.get("stat_url").format(league=league),
            method=self.book_data.method,
            headers=headers
        )

        if not stats or len(stats.get("data", [])) == 0:
            return []

        valid_stats = [
            stat.get("id")
            for stat in stats.get("data", [])
        ]

        if not valid_stats:
            return []

        tasks = [
            self.api_caller(
                session=session,
                url=self.book_data.url.get("game_url").format(market_id=stat),
                method=self.book_data.method,
                headers=headers
            )

            for stat in valid_stats
        ]

        return await asyncio.gather(*tasks)


    def _extract_game_data(self, game_data):
        team_a = game_data.get("game", {}).get("homeTeam", {}).get("alias")
        team_b = game_data.get("game", {}).get("awayTeam", {}).get("alias")
        player_team = game_data.get("player", {}).get("teamAlias")
        player_name = f"{game_data.get('player').get('firstName')} {game_data.get('player').get('lastName')}"
        start_date = self.cache_time(datetime.fromtimestamp(game_data.get("game").get("date") / 1000).isoformat())

        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([player_name, start_date])

        options = ["over", "under"] if game_data.get("pickOptions") == "MORE_OR_LESS" else ["over"]
        discounts = Discounts(
            discount_name="Discount",
            discount_percentage=game_data.get("discount", {}).get("discountPercentage"),
            discount_expiry=self.cache_time(datetime.fromtimestamp(game_data.get("discount", {}).get("expiry") / 1000).isoformat())
        ) if game_data.get("isDiscounted") else {}

        return PlayerData(
            player_name=self.clean_and_normalize_name(player_name),
            league=LEAGUES.get(game_data.get("sport").lower(), game_data.get("sport").upper()),
            start_date=start_date,
            team_data=TeamData(
                team_a=self.clean_and_normalize_name(team_a),
                team_b=self.clean_and_normalize_name(team_b),
                team_key=team_key,
                player_team=self.clean_and_normalize_name(player_team),
            ),
            future=False,
            stats=[
                Stats(
                   stat_type=STAT_TYPES.get(game_data.get("marketType").get("name").lower(), game_data.get("marketType").get("name")),
                    line=game_data.get("line").get("balancedLine") if not game_data.get("isDiscounted") else game_data.get("discount").get("discountLine"),
                    bet_direction=option,
                    regular_line=not game_data.get("isDiscounted"),
                    discounts=discounts
                )

                for option in options
            ],
            solo_game=False if all([team_a, team_b]) else True
        )


    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            auth_token = await self.redis.get_auth_token("ownerbox_auth_token")
            await self.redis.close()

            if not auth_token:
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
                self._api_call_log(sportsbook="ownerbox", error_details="No data found in API responses")
                return

            player_data_list = {}
            for game_details in merged_data:
                player_data = self._extract_game_data(game_details)
                if player_data:
                    player_key = (
                        player_data.player_name,
                        player_data.team_data.team_a,
                        player_data.team_data.team_b,
                        player_data.start_date,
                    )

                    if player_key in player_data_list:
                        player_data_list[player_key].stats.extend(player_data.stats)
                    else:
                        player_data_list[player_key] = player_data

            ownerbox_data = list(player_data_list.values())
            return await self._database_mapper(ownerbox_data)

if __name__ == "__main__":
    ob = Ownerbox()
    asyncio.run(ob.run_book())