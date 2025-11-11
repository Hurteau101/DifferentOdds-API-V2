import json

import aiohttp
from dotenv import load_dotenv
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Redis.redis_manager import RedisManager
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, TeamData, Stats, OptionalStatInformation
import asyncio

class FanDuelPicks(DFSBookBase):
    VALID_LEAGUES = ["NFL", "MLB"]
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="fanduel_picks")
        load_dotenv()
        self.redis = RedisManager(db=5)

    def _extract_data(self, raw_data, league):
        player_data = raw_data.get("prop").get("competitor", {})
        team_data = raw_data.get("prop").get("fixture")
        first_name = player_data.get("firstNames", "")
        last_name = player_data.get("lastName", "")
        player_team = self.clean_and_normalize_name(player_data.get("team", {}).get("name"))
        start_date = self.cache_time(team_data.get("startsAt"))
        team_a = self.clean_and_normalize_name(team_data.get("homeTeam", {}).get("name"))
        team_a_abbreviation = team_data.get("homeTeam", {}).get("abbreviation", "")
        team_b = self.clean_and_normalize_name(team_data.get("awayTeam", {}).get("name"))
        team_b_abbreviation = team_data.get("awayTeam", {}).get("abbreviation", "")
        stat_type = raw_data.get("gameGroupMarket", {}).get("displayName").lower()

        if team_a and team_b:
            team_key = self._generate_key([team_a, team_b, start_date])
        else:
            team_key = self._generate_key([f"{first_name} {last_name}", start_date])

        over_under_mapper = {
            "MORE": "over",
            "LESS": "under"
        }

        return PlayerData(
            player_name=f"{first_name} {last_name}",
            league=LEAGUES.get(league.lower(), league.upper()),
            start_date=start_date,
            team_data=TeamData(
                team_a=team_a,
                team_a_abbreviation=team_a_abbreviation,
                team_b=team_b,
                team_b_abbreviation=team_b_abbreviation,
                player_team=player_team,
                team_key=team_key
            ),
            future=False,
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(stat_type.lower(), stat_type.title()),
                    line=raw_data.get("line"),
                    bet_direction=over_under_mapper.get(direction.get("selection", {}).get("type"), "N/A"),
                    regular_line=True if direction.get("oddsRangeType") == "REGULAR" else False,
                    optional_stats=OptionalStatInformation(
                        odds_type="Standard" if direction.get("oddsRangeType") == "REGULAR" else "Spicy",
                        internal_id=direction.get("id")
                    ),
                )
                for direction in raw_data.get("gameGroupSelections", [])
            ],
            solo_game=False
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:

            auth_token = await self.redis.get_auth_token("fanduel_picks_auth_token")
            await self.redis.close()

            if not auth_token:
                self.file_logger.log(
                    sportsbook="fanduel_picks",
                    message="No auth token found for FanDuel Picks",
                    level="ERROR",
                    additional_information="Ensure to run the auth token retriever script",
                )

                return

            headers = self.book_data.headers
            headers.update({
                "Cookie": f"X-Auth-Token={auth_token}"
            })

            # MULTIPLIER ENDPOINT

            # id_list = [
            #     "019a6998-a9e1-7c39-9dec-21b481810eeb", "019a6865-3586-7551-8b2d-e7955ad9ac88", "019a6865-3586-7650-b111-2036a8029860",
            # ]
            #
            # data = await self.api_caller(
            #     session=session,
            #     url=self.book_data.url.get("multi"),
            #     method=self.book_data.method,
            #     headers=headers,
            #     params={
            #         'lineup': json.dumps(id_list),
            #         '_data': 'routes/api+/bonus-multiplier'
            #     }
            # )
            #
            # print(data)

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url").format(league=league),
                    method=self.book_data.method,
                    headers=headers
                )
                for league in FanDuelPicks.VALID_LEAGUES
            ]

            raw_results = await asyncio.gather(*tasks)

            results = self.check_api_response(sportsbook="fanduel_picks", results=raw_results)

            if not results:
                return

            game_ids = [
                {
                    "league": result.get("sport"),
                    "game_id": data.get("id")
                }
                for result in results
                for data in result.get("gameGroupsForCompetition", [])
            ]

            stat_tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("stat_url").format(game_id=game["game_id"]),
                    method=self.book_data.method,
                    headers=headers
                )
                for game in game_ids
            ]

            raw_results = await asyncio.gather(*stat_tasks)
            results = self.check_api_response(sportsbook="fanduel_picks", results=raw_results)

            if not results:
                return

            merge_data = [
                {
                    "league": game["league"],
                    "game_id": game["game_id"],
                    "data": resp
                }
                for game, resp in zip(game_ids, results)
            ]


            player_data_list = {}

            for sports_data in merge_data:
                for game_details in sports_data.get("data").get("gameGroupProps", []):
                    player_data = self._extract_data(game_details, sports_data.get("league"))
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

            fanduel_picks_data = list(player_data_list.values())
            return await self._database_mapper(fanduel_picks_data)


if __name__ == "__main__":
    fanduel = FanDuelPicks()
    asyncio.run(fanduel.run_book())