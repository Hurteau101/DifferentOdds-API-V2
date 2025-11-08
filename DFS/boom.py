import re
import aiohttp
import asyncio
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import Stats, OptionalStatInformation, PlayerData, TeamData


class Boom(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="boom")


    # Extract the multiplier from the stat list. 1st float found is the multiplier.
    def _get_multiplier(self, stat_list):
        for item in stat_list:
            if isinstance(item, float):
                return item
        return None

    # Extract the market type from the market name. This splits on camel case.
    def _get_market_type(self, market_name):
        new_text = re.sub(r'([A-Z])', r' \1', market_name)
        return new_text.strip()

    def _extract_game_data(self, game_data):
        if not game_data:
            return []

        league = LEAGUES.get(game_data.get("league").lower(), game_data.get("league").upper())
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
            stat_list = []

            for player_stats in player_data.get("q"):
                if player_stats.get("status") != "available":
                    continue


                if len(player_stats.get("searchTerms")) > 0:
                    stat_type = player_stats.get("searchTerms")[0]
                else:
                    stat_type = player_stats.get("statistic").lower().replace("_", " ").replace("prizepicks", "").strip()

                # These are all the different information that are used in esports, so we need to handle them differently.
                if is_esports:
                    player_name = player_data.get("title").get("o").get("name").lower()
                    stat_title = player_stats.get("title").lower().replace(player_name, "").replace(" |", "").strip()

                    # Condition added as there is a conflict of mapping with other books
                    if stat_title.lower == "walks":
                        stat_title = "pitcher walks"

                    stat_type = STAT_TYPES.get(stat_title, stat_title.title())
                    league = LEAGUES.get(esport_check[-1].lower(), esport_check[-1].upper())

                stat_list.extend(
                    Stats(
                        stat_type=STAT_TYPES.get(stat_type.lower(), stat_type.title()),
                        line=stat.get("l"),
                        bet_direction=next(
                            (bet for bet in direction if bet in ("over", "under")),
                            None
                        ),
                        regular_line=True if self._get_multiplier(direction) == 1.00 else False,
                        optional_stats=OptionalStatInformation(
                            market_type= market_type,
                            multiplier=self._get_multiplier(direction),
                        )
                    )

                    for stat in player_stats.get("c", [])
                    for direction in stat.get("c", [])
                )


            team_a = player_data.get("playerImage", {}).get("abbreviation")
            team_b = player_data.get("gameInfo", {}).get("o", {}).get("opponentAbbreviation")
            start_date = self.cache_time(player_data.get("timeInfo", {}).get("o", {}).get("date", ""))

            if team_a and team_b:
                team_key = self._generate_key([team_a, team_b, start_date])
            else:
                team_key = self._generate_key([player_name, start_date])


            player_list.append(PlayerData(
                player_name=player_name,
                league=league,
                start_date= start_date,
                future=True if market_type == "full Season" else False,
                team_data=TeamData(
                    team_a=self.clean_and_normalize_name(team_a),
                    team_b=self.clean_and_normalize_name(team_b),
                    player_team=self.clean_and_normalize_name(team_a),
                    team_key=team_key
                ),
                stats=stat_list,
                solo_game=False if all([team_a, team_b]) else True,
            ))

        return player_list

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
            )

            api_data = self.check_api_response(sportsbook="boom", results=raw_api_data)
            if not api_data:
                return

            results = [
                self._extract_game_data(game_data=game_details)
                for game_details in api_data.get("data").get("multiLineContest").get("sections")
            ]

            results = [player for sublist in results for player in sublist]
            return await self._database_mapper(results)


if __name__ == "__main__":
    boom = Boom()
    data = asyncio.run(boom.run_book())