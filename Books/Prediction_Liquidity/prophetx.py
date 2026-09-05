import asyncio
import os
import re
from itertools import batched
from Books.Bases.prediction_base import PredictionBookBase
from LoggingHelper.logging_helper import ErrorTypes, insert_log
from Settings.Models.base_models import GameData, OddsFormat
from Settings.Models.prediction_liquidity_models import PredictionLiquidityStats, LiquidityData
from curl_cffi import AsyncSession as CurlAsyncSession

class Prophetx(PredictionBookBase):
    def __init__(self):
        super().__init__(book_name="prophetx")


    def extract_event_data(self, raw_event_data: dict) -> dict:
        return {
            event.get("event_id"): {
                "event_name": event.get("display_name") or event.get("name"),
                "teams": {
                    team.get("side"): {
                        "name": team.get("name"),
                        "abbreviation": team.get("abbreviation"),
                    }
                    for team in event.get("competitors", [])
                },
                "start_date": event.get("scheduled"),
                "league": event.get("tournament_name"),
            }
            for event in raw_event_data.get("data", {}).get("sport_events", [])
            if event.get("status") == "not_started"
               and not event.get("sub_type")  # Sub Type is futures
        }


    def extract_markets(self, market_data: dict, event_data: dict, event_id: str):
        def normalize_tennis(league):
            if not league:
                return league

            return re.sub(r'^(WTA|ATP)\s+.*', r'\1', league, flags=re.IGNORECASE)

        event_information = event_data.get(int(event_id)) or event_data.get(event_id)
        if event_information is None:
            print(f"No event information found for event id: {event_id}")
            return

        raw_league = event_information.get("league")
        league = normalize_tennis(raw_league)

        game_data = GameData(
            league=league,
            start_date=event_information.get("start_date"),
            game_key=event_information.get("event_name"),
            team_a=event_information.get("teams", {}).get("home", {}).get("name"),
            team_b=event_information.get("teams", {}).get("away", {}).get("name"),
            team_a_abbreviation=event_information.get("teams", {}).get("home", {}).get("abbreviation"),
            team_b_abbreviation=event_information.get("teams", {}).get("away", {}).get("abbreviation"),
            odds=[],
        )
        for market in market_data:
            if market.get("player_id"):
                display_name = market.get("display_name", "")
                # We can be more lient here since we have mapping if we cut off the name a bit.
                player_name =  " ".join(display_name.split(" ")[0:2])
                stat_type = market.get("category_name")
            else:
                player_name = None
                stat_type = market.get("display_name")


            for selection_list in market.get("selections", []):
                prediction_data = {
                    "market": stat_type,
                    "liquidity_data": []
                }

                for index,selection in enumerate(selection_list, start=1):
                    liquidity = selection.get("value")
                    if not liquidity or liquidity <= 0:
                        continue

                    if "over" in selection.get("display_name") or "under" in selection.get("display_name"):
                        bet_type = selection.get("display_name").split(" ")[0]
                        bet_team = None
                    else:
                        bet_type = None
                        bet_team = re.sub(r"\s[+-].*$", "", selection.get("name"))

                    prediction_data.update({
                        "line": selection.get("line") if selection.get("line") != 0 else None,
                        "bet_type": bet_type,
                        "bet_team": bet_team,
                        "bet_player": player_name,
                        "future": False,
                    })

                    prediction_data["liquidity_data"].append(LiquidityData(
                        odds_format=OddsFormat(american_odds=selection.get("odds")),
                        liquidity=selection.get("value"),
                        is_best=True if index == 1 else False,
                        additional_information={
                            "adjusted_odds": selection.get("adjusted_odds"),
                            "stake": selection.get("stake")
                        }
                    ))

                if not prediction_data["liquidity_data"]:
                    continue

                stats = PredictionLiquidityStats(**prediction_data, league=league)
                stats.market = self.special_stat_mapper(stats.market, league)
                game_data.odds.append(stats)
                # game_data.odds.append(PredictionLiquidityStats(**prediction_data))


        return game_data

    async def run_book(self) -> list | None:
        api_key = os.getenv("PROPHETX_API_KEY")
        if not api_key:
            raise ValueError("PROPHETX_API_KEY is not set in the environment variables.")

        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            new_headers = {"Authorization": api_key}

            events = await self.api_caller(
                session=session,
                url=self.book_data.url.get("events_url"),
                method=self.book_data.method,
                headers=new_headers
            )

            event_data = self.extract_event_data(events)

            event_ids_batched = [list(batch) for batch in batched(event_data.keys(), 65)]

            market_data = await asyncio.gather(
                *(
                    self.api_caller(
                        session=session,
                        url=self.book_data.url.get("markets_url"),
                        method=self.book_data.method,
                        headers=new_headers,
                        params={
                            "event_ids": ",".join(map(str, event_ids_list)),
                            "get_all_market": "true"
                        }
                    )
                    for event_ids_list in event_ids_batched
                )
            )

            game_data = []

            for market in market_data:
                market_data = market.get("data", {})
                for event_id, event_info in market_data.items():
                    data = self.extract_markets(
                        event_info, event_data, event_id
                    )

                    if data:
                        game_data.append(data)

            if not game_data:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.NO_EXTRACTION_DATA,
                    error_message="No event data found"
                )
                return None


            await self.store_data(
                data_to_store=game_data,
                key_name=self.book_data.name
            )

            await self.flush_unmapped()
            return game_data



if __name__ == "__main__":
    book = Prophetx()
    asyncio.run(book.run_book())