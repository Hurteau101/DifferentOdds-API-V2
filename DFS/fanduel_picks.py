import os
import aiohttp
import json
import httpx
import requests
from celery.bin.result import result
from dotenv import load_dotenv
from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from datetime import datetime, timedelta
from Settings.dfs_model import PlayerData, TeamData, Stats, OptionalStatInformation


class FanDuelPicks(DFSBookBase):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join(BASE_DIR, "..", "Settings", "auth_tokens.json")
    VALID_LEAGUES = ["NFL", "MLB"]
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="fanduel_picks")
        load_dotenv()
        self._check_token()


    def _check_token(self):
        # Load existing token data
        with open(FanDuelPicks.relative_path, "r") as f:
            token_data = json.load(f)

        if not token_data.get("fanduel_picks"):
            self.file_logger.log(
                message=f"No auth token found for FanDuel Picks. Please set the token in auth_tokens.json",
                level="ERROR",
            )

        auth_token = token_data.get("fanduel_picks", {}).get("auth_token")
        auth_expiry = token_data.get("fanduel_picks", {}).get("expiry")

        # Check if token is missing or expired and generate a new one if needed
        if not auth_token or self._check_auth_expiration(auth_expiry):
            new_auth = self._generate_new_auth()
            token_data["fanduel_picks"] = new_auth
            with open(FanDuelPicks.relative_path, "w") as f:
                json.dump(token_data, f, indent=4, default=str)

    def _check_auth_expiration(self, expiry):
        # If expiry is None or empty, consider it expired
        if not expiry:
            return True

        # Convert the expiry string to a datetime object and compare with current time. If current time is greater, it's expired.
        auth_expiry = datetime.fromisoformat(expiry)
        date_now = datetime.now()
        return date_now >= auth_expiry

    def _generate_new_auth(self):
        url = "https://api.fanduel.com/sessions"
        headers = {
            'X-Installation-id': '4F447867-D1A7-458E-8566-733351B5BB58',
            'Authorization': 'Basic ODc2YmQzOTE3ZWE3NjYwMjZhNjg5YzY2MTE5OGQxMmU6',
            'Origin': 'https://account.picks.fanduel.com',
            'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_7_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AppInfo (appDomain/picks; version/3.1.0; platform/ios)',
            'Referer': 'https://account.picks.fanduel.com/',
            'x-px-context': '_px3=99705c3762b3d26c2f7e4516c14c73b857d17593e997f68a14635d27a78c5103:3ThPM+kI8SNJ0Tcl6TLwv64UqGl9vfZAb0DpdSnx0tLUtOc1ge6wpgSE7SEtRun/u1tLods2UuMnfZhZmqkkKQ==:1000:ml+mfrodK+i+NvDYjFoiQniMV4AeS19X8pjfRuMg0wRsv0P3DnlDz1hhfRTcXRqfSUL5oYb4QuhGOZ5Kb7MHufC0F2nyOdcqkfICIjmJm6BJR+HfGuvHfSNbfrdavrh/oO4qY36e2Pm+wOt4qlHCUFWneW/bIatzEz+kivxE9c9UtQ9yBIUVaJoA2bCnY9GiDbweJONTWpqfk9gAjK3ae8v6+meYAPFUt28JB6dPh3k=;pxcts=6e9a5a65-8e5c-11f0-bebf-b69a35fb55c1',
            'Content-Type': 'application/json'
        }

        payload = {
            "email": os.getenv("FANDUEL_PICK_EMAIL"),
            "password": os.getenv("FANDUEL_PICK_PASSWORD"),
            "product": os.getenv("FANDUEL_PICK_PRODUCT"),
        }

        # Make the POST request to generate a new auth token - Using httpx for HTTP/2 support
        with httpx.Client(http2=True) as client:  # HTTP/2 enabled
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 201:
                data = response.json()

                auth_token = next((
                    auth_data.get("id")
                    for auth_data in data.get("sessions", [])
                ), None)

                if auth_token:
                    return{
                        "auth_token": auth_token,
                        "expiry": (datetime.now() + timedelta(hours=23)).isoformat()
                    }

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
                    ),
                )
                for direction in raw_data.get("gameGroupSelections", [])
            ],
            solo_game=False
        )


    # async def _extract_ids(self, league, session):
    #     api_data = await self.api_caller(
    #         session=session,
    #         url=self.book_data.url.get("main_url").format(league=league),
    #         method=self.book_data.method,
    #         headers=self.book_data.headers
    #     )
    #
    #     # Keeping this in, you don't need market strings, but may in the future.
    #     # market_string = ",".join({
    #     #     market.get("id")
    #     #     for market in api_data.get("markets", [])
    #     # })
    #
    #     return [
    #         data.get("id")
    #         for data in api_data.get("gameGroupsForCompetition", [])
    #     ]

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            with open(FanDuelPicks.relative_path, "r") as f:
                token_data = json.load(f)

            auth_token = token_data.get("fanduel_picks", {}).get("auth_token")
            if not auth_token:
                self.file_logger.log(
                    message=f"No auth token found for FanDuel Picks. Please set the token in auth_tokens.json",
                    additional="run_book caller",
                    level="ERROR",
                )
                return

            headers = self.book_data.headers
            headers.update({
                "Cookie": f"X-Auth-Token={auth_token}"
            })

            tasks = [
                self.api_caller(
                    session=session,
                    url=self.book_data.url.get("main_url").format(league=league),
                    method=self.book_data.method,
                    headers=headers
                )
                for league in FanDuelPicks.VALID_LEAGUES
            ]

            results = await asyncio.gather(*tasks)
            if not results:
                self._api_call_log("fanduel_picks")
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

            results = await asyncio.gather(*stat_tasks)
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
    import asyncio
    asyncio.run(fanduel.run_book())