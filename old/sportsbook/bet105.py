import json
import re
from datetime import datetime, timezone
import aiohttp

from orjson import orjson

from old.Mapper.static_mapper import STAT_TYPES
from old.Redis.redis_manager import RedisSync
from old.Settings.Sportsbook_Settings.sportsbook_book_base import SportsbookBase
from old.Settings.book_base import SportbookRequestType
import asyncio

from old.Settings.Sportsbook_Settings.sportsbook_model import GameData, TeamData, Markets


class Bet105(SportsbookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="bet105")
        self.mapped_data = self._load_mapped_data()
        # with open("kibl_mapped.json", "w") as file:
        #     json.dump(self.mapped_data, file, indent=4)

        self.non_market = [] # DEBUGGING

    def get_auth(self):
        """Retrieve the authentication token from Redis"""
        redis = RedisSync(db=5)
        return redis.get("kibl_auth_token").decode("utf-8") if redis.get("kibl_auth_token") else None

    def _load_mapped_data(self):
        """Load mapped data from Redis"""
        redis = RedisSync(db=2)
        raw_mapped =  redis.get("kibl_mapper_data")
        return orjson.loads(raw_mapped) if raw_mapped else {}

    def chunk(self, base_list, chunk_size):
        """Helper method to chunk a list into smaller lists of a specified size"""
        for i in range(0, len(base_list), chunk_size):
            yield base_list[i:i + chunk_size]

    def _extract_data(self, market_data: dict, book_name: str):
        if market_data.get("is_live") or all([market_data.get("price_american"), market_data.get("price_decimal"),
                                              market_data.get("price_fractional")]):
            return {}

        return {
            "book_name": book_name,


        }

    def yeild_markets(self, results: list):
        """Helper generator to yield markets from market data"""
        for result in results:
            if result and result.get("success") and result.get("result"):
                for markets in result.get("result", []):
                    for market in markets.get("participants", []):
                        yield market

    def yeild_fixtures(self, results: list):
        for result in results:
            if result and result.get("success") and result.get("result"):
                for fixture_result in result.get("result", []):
                    yield fixture_result

    def _validate_game_date(self, game_date: str) -> bool:
        current_date = datetime.now(timezone.utc)
        game_date_obj = datetime.strptime(game_date, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

        if current_date > game_date_obj:
            return False

        return True


    def _extract_fixtures(self, raw_fixture_data: list, event_names: dict):
        fixture_results = {}

        for fixture in self.yeild_fixtures(raw_fixture_data):
            game_date = self.cache_time(fixture.get("start_time"))
            if not self._validate_game_date(game_date):
                continue

            parent_fixture_id = fixture.get("parent_fixture_id")
            fixture_id = fixture.get("fixture_id")

            parent_data = {
                "league_id": fixture.get("league_id"),
                "event_name": event_names.get(parent_fixture_id, Bet105.clean_name(fixture.get("name", ""))),
                "league": (
                    self.mapped_data.get("leagues", {})
                    .get(str(fixture.get("league_id")), {})
                    .get("league_abbr")
                    if fixture.get("league_id")
                    else ""
                ),
                "parent_fixture_id": parent_fixture_id,
                "start_date": game_date,
                "participants_dict": {}
            }

            participants_dict = {
                int(participant.get("participant_id")): participant.get("name")
                for participant in fixture.get("participants", [])
            }

            fixture_results.setdefault(fixture_id, {
                "name": Bet105.clean_name(fixture.get("name")),
                "fixture_id": fixture.get("fixture_id"),
                "fixture_type_id": fixture.get("fixture_type_id"),
                "information_id": next((
                    information.get("fixture_information_id")
                    for information in fixture.get("informations", [])
                ), None),
                "participants":[
                    {
                        participant.get("participant_id"):participant.get("name")
                    }
                    for participant in fixture.get("participants", [])
                ],
                "parent_data": {**parent_data, "participants_dict": participants_dict},
            })

        return fixture_results

    @staticmethod
    def clean_name(name: str):
        """Function to help clean names, as sometimes they begin with numbers"""
        if not name:
            return ""

        return re.sub(r'^[\d\-]+\s*', '', name).strip()

    async def _get_events(self, session: aiohttp.ClientSession, sportsbook_id: int):
        """Get the event names"""
        raw_event_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("events"),
            params={
                "feed_source_id": sportsbook_id
            },
            headers=self.book_data.headers,
            method=self.book_data.method
        )

        if not raw_event_data and not raw_event_data.get("success") and not raw_event_data.get("result"):
            return None

        return {
            result.get("fixture_id"): Bet105.clean_name(result.get("feed_name"))
            for result in raw_event_data.get("result", [])
            if result.get("is_active") and any(event_name in result.get("feed_name") for event_name in ["vs", "at"])
        }


    async def _book_runner(self, session: aiohttp.ClientSession, sportsbook_name: str, sportsbook_id: int):
        """Helper method to run each book through the process"""
        events = await self._get_events(session=session, sportsbook_id=sportsbook_id)
        if not events:
            return None

        leagues = self.mapped_data.get("leagues", {})

        raw_data = [
            self.api_caller(
                session=session,
                url=self.book_data.url.get("fixtures"),
                params={
                    "league_id": ",".join(map(str, league_chunk))
                },
                headers=self.book_data.headers,
                method=self.book_data.method
            )
            for league_chunk in self.chunk(list(leagues.keys()), 14)
        ]

        results = await asyncio.gather(*raw_data)
        fixtures = self._extract_fixtures(results, events)


        league_set = set(
            fixture_data.get("parent_data", {}).get("league_id")
            for fixture_data in fixtures.values()
        )

        raw_data = [
            self.api_caller(
                session=session,
                url=self.book_data.url.get("markets"),
                params={
                    "league_id": ",".join(map(str, league_chunk)),
                    "feed_source_id": sportsbook_id
                },
                headers=self.book_data.headers,
                method=self.book_data.method
            )
            for league_chunk in self.chunk(list(league_set), 14)
        ]

        market_results = await asyncio.gather(*raw_data)
        if not market_results:
            return



        data_dict = {}

        for market in self.yeild_markets(market_results):
            data = self._extract_market_data(market, fixtures, sportsbook_name)
            if data:
                key=data.team_data.team_key

                if key in data_dict:
                    data_dict[key].odds.extend(data.odds)
                else:
                    data_dict[key] = data

        return list(data_dict.values())


    def _extract_market_data(self, market_data: dict, fixture_data: dict, sportsbook_name: str):
        if market_data.get("max_limit") == 250.0:
            return

        if market_data.get("is_live") or not market_data.get("is_current"):
            return

        fixture = fixture_data.get(market_data.get("fixture_id"))

        if not fixture or not market_data.get("price_american"):
            self.non_market.append(market_data)
            return None

        parent_dict = fixture.get("parent_data", {})

        if "props" in fixture.get("name").lower():
            teams = parent_dict.get("event_name").split(" vs ")
            key = self._generate_key([teams[0], teams[1], parent_dict.get("start_date")])

            team_data = TeamData(
                team_a=teams[0].strip(),
                team_b=teams[1].strip(),
                team_key=key.replace(" ", "_"),
            )
        elif len(fixture.get("participants")) <= 2:
            teams = fixture.get("participants")
            team_list = [
                team
                for participant in teams
                for team in participant.values()
            ]
            key = self._generate_key([team_list[0], team_list[1], parent_dict.get("start_date")]) if len(teams) == 2 else (
                self._generate_key([team_list[0], parent_dict.get("start_date")]))

            team_data = TeamData(
                team_a=team_list[0].strip(),
                team_b=team_list[1].strip() if len(teams) == 2 else None,
                team_key=key.replace(" ", "_"),
            )
        else:
            team_data = TeamData(
                team_key=f"{parent_dict.get('event_name')}_{parent_dict.get('start_date')}".replace(" ", "_"),
            )


        bet_type = self.mapped_data.get("sides").get(str(market_data.get("side_id")))

        if bet_type not in ("over", "under"):
            bet_type = None

        market = self.mapped_data.get("market_types").get(str(market_data.get("market_type_id")), "Unknown Market")
        segment = self.mapped_data.get("segments", {}).get(str(market_data.get("segment_id")))
        mapped_segment = STAT_TYPES.get(segment.lower(), segment)

        final_market = f"{mapped_segment} {market}" if segment.lower() != "full game" else market

        fixture_type = self.mapped_data.get("fixture_types").get(str(fixture.get("fixture_type_id")))

        bet_team = parent_dict.get("participants_dict", {}).get(market_data.get("participant_id")) if market_data.get("participant_id") and fixture_type != "Proposition" else None

        if "spread" in final_market.lower():
            line = market_data.get("point")
        else:
            line = market_data.get("point") if market_data.get("point") != 0.0 else None

        return GameData(
            book_name=sportsbook_name,
            start_date=parent_dict.get("start_date"),
            league=parent_dict.get("league"),
            team_data=team_data,
            event_name=parent_dict.get("event_name"),
            odds=[
                Markets(
                    market=final_market,
                    american_odds=market_data.get("price_american"),
                    bet_team=bet_team,
                    bet_type=bet_type,
                    line=line,
                    ids=market_data,
                    bet_player=parent_dict.get("participants_dict", {}).get(market_data.get("participant_id")) if fixture_type == "Proposition" else None,
                    future=True if fixture_type == "Futures" else False,
                )
            ],
        )

    async def run_book(self):
        auth_token = self.get_auth()

        if not auth_token:
            return

        if not self.mapped_data:
            return

        async with aiohttp.ClientSession() as session:
            self.book_data.headers["Authorization"] = auth_token

            ## Keep in here until other sportsbooks are implemented
            sportsbooks_single = [
                {
                    "book_name": "bet105",
                    "feed_source_id": 171
                }
            ]


            sportsbook_tasks = [
                self._book_runner(session=session, sportsbook_name=book.get("book_name"), sportsbook_id=book.get("feed_source_id"))
                # for book in self.mapped_data.get("sportsbooks", [])
                for book in sportsbooks_single
            ]

            results = await asyncio.gather(*sportsbook_tasks)
            results = [item for sublist in results if sublist for item in sublist]

            return results


if __name__ == "__main__":
    sportsbook = Bet105()
    asyncio.run(sportsbook.run_book())
