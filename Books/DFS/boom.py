import re
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData
from Utils.request_caller import SportbookRequestType


class Boom(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="boom", request_type=SportbookRequestType.ASYNC)

    # Extract the multiplier from the stat list. 1st float found is the multiplier.
    def _get_multiplier(self, stat_list: list) -> float | None:
        for item in stat_list:
            if isinstance(item, float):
                return item
        return None

    # Extract the market type from the market name. This splits on camel case.
    def _get_market_type(self, market_name: str) -> str:
        new_text = re.sub(r'([A-Z])', r' \1', market_name)
        return new_text.strip()

    def _extract_game_data(self, game_data: dict) -> list:
        if not game_data:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="game_data_failure",
                message="Game data extraction received no data",
                level="error"
            )

            return []

        league = game_data.get("league")
        player_list = []

        # Esports is handle a bit differently in the backend, so we must ensure to check if its an esports game.
        is_esports = False

        esport_check = league.lower().split("_")
        if len(esport_check) > 1 and esport_check[0] == "autoesports":
            is_esports = True

        for player_data in game_data.get("qG"):
            player_name = f"{player_data.get('title').get('o').get('firstName', '').strip()} {player_data.get('title').get('o').get('lastName', '').strip()}" if player_data.get(
                'title') else ""
            market_type = self._get_market_type(player_data.get("periodClassifier"))

            team_a = player_data.get("playerImage", {}).get("abbreviation")
            team_b = player_data.get("gameInfo", {}).get("o", {}).get("opponentAbbreviation")
            start_date = player_data.get("timeInfo", {}).get("o", {}).get("date", "")

            if team_a and team_b:
                team_key = Boom.generate_key([team_a, team_b, start_date])
            else:
                team_key = Boom.generate_key([player_name, start_date])

            stat_list = []

            for player_stats in player_data.get("q"):
                if player_stats.get("status") != "available":
                    continue

                if len(player_stats.get("searchTerms")) > 0:
                    stat_type = player_stats.get("searchTerms")[0]
                else:
                    stat_type = player_stats.get("statistic").lower().replace("_", " ").replace("prizepicks",
                                                                                                "").strip()

                # These are all the different information that are used in esports, so we need to handle them differently.
                if is_esports:
                    player_name = player_data.get("title").get("o").get("name").lower()
                    stat_title = player_stats.get("title").lower().replace(player_name, "").replace(" |",
                                                                                                    "").strip()

                    # Condition added as there is a conflict of mapping with other books
                    if stat_title.lower == "walks":
                        stat_title = "pitcher walks"

                    stat_type = stat_title
                    league = esport_check[-1].lower()

                stat_list.extend(
                    DFSStats(
                        player_name=player_name,
                        player_team=team_a,
                        stat_type=stat_type.lower(),
                        future=True if market_type == "full Season" else False,
                        line=stat.get("l"),
                        bet_type=next(
                            (bet for bet in direction if bet in ("over", "under")),
                            "N/A" # Change to None
                        ),
                        regular_line=True if self._get_multiplier(direction) == 1.00 else False,
                        optional_stats=OptionalStatInformation(
                            market_type=market_type,
                            multiplier=self._get_multiplier(direction),
                        )
                    )

                    for stat in player_stats.get("c", [])
                    for direction in stat.get("c", [])
                )



            player_list.append(GameData(
                league=league,
                game_key=team_key,
                start_date=start_date,
                team_data=TeamData(
                    team_a=team_a,
                    team_b=team_b,
                ),
                odds=stat_list,
                solo_game=False if all([team_a, team_b]) else True,
            ))

        return player_list

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
            )

            if not api_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="Main API URL returned no data",
                    level="error"
                )

                return

            results = [
                self._extract_game_data(game_data=game_details)
                for game_details in api_data.get("data").get("multiLineContest").get("sections")
            ]

            events = {}
            for game_data in self.yield_game_data(book_data=results):
                self.add_to_events(events, game_data, GameData)

            boom_data = list(events.values())
            mapped_data = await self.map_runner(session=session, sportsbook_data=boom_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data
