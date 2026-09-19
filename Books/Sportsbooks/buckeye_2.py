import asyncio
import os
from collections import defaultdict
from datetime import datetime
from itertools import chain
from typing import Callable
from zoneinfo import ZoneInfo
import aiohttp
from dotenv import load_dotenv
from requests_toolbelt.utils.formdata import urlencode

from Books.Bases.pph_base import PPHBookBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Redis.redis_manager import RedisAsyncManager
from Settings.Models.base_models import GameData, OddsFormat, TeamData
from Settings.Models.sportsbooks_models import SportsbookStats
from curl_cffi import AsyncSession as CurlAsyncSession


class Buckeye2(PPHBookBase):
    def __init__(self):
        super().__init__(book_name="buckeye2")

    def _filter_leagues(self, league_info: list):
        """Only include leagues that are in the accepted_sub_type_display list."""
        leagues = []

        for league in league_info:
            sport_sub_type_display = league.get("SportSubTypeDisplay", "").strip().lower()
            matching_config = next((
                {mapped_name: config.get("accepted_sub_type_display", {}).get(sport_sub_type_display)}
                for mapped_name, config in self.mapping_configs.items()
                if sport_sub_type_display in config.get("accepted_sub_type_display", {})
            ), None)

            if not matching_config:
                continue

            leagues.append({
                "sport_type": league.get("SportType"),
                "sport_subtype": league.get("SportSubType"),
                "period_description": league.get("PeriodDescription"),
                "period_number": league.get("PeriodNumber"),
                "mapped_name": next(iter(matching_config)),
                "game_type": next(iter(matching_config.values()))
            })

        return leagues

    # This is used for the dropdowns on the website.
    async def get_buy_points(self, username: str, auth_token: str, sport_type: str, sport_subtype: str):
        return await self.api_caller(
            url=self.book_data.url.get("point_group"),
            use_proxy=True,
            method=self.book_data.method,
            headers={
                **self.book_data.headers,
                "Authorization": f"Bearer {auth_token}"
            },

            json={
                "customerID": f"{username}_0",
                "wagerType": "Straight",
                "sportType": sport_type,
                "sportSubType": sport_subtype,
                "RRO": ''
            }

        )

    async def market_caller(self, username: str, auth_token: str, league: dict):
        sport_type = league.get("sport_type")
        sport_subtype = league.get("sport_subtype")

        market_data = await self.api_caller(
            url=self.book_data.url.get("markets"),
            use_proxy=True,
            headers={
                **self.book_data.headers,
                "Authorization": f"Bearer {auth_token}"
            },
            method=self.book_data.method,
            json={
                "customerID": f"{username}_0",
                "operation": "Get_LeagueLines2",
                "sportType": sport_type,
                "sportSubType": sport_subtype,
                "period": league.get("period_description"),
                "hourFilter": "0",
                "propDescription": "",
                "wagerType": "Straight",
                "keyword": "",
                "office": "WAGERHOME",
                "correlationID": "",
                "periodNumber": league.get("period_number"),
                "periods": "0",
                "rotOrder": "0",
                "placeLateFlag": "false",
                "RRO": "1",
                "agentSite": "0",
            }
        )

        buy_points = await self.get_buy_points(username=username, auth_token=auth_token, sport_type=sport_type,sport_subtype=sport_subtype)

        if buy_points:
            buy_points_key = buy_points.get("BuyPoints", {})
            market_data["buypoints"] = {
                "Spread": {
                    "amount": buy_points_key.get("SpreadBuy", 0),
                    "max": buy_points_key.get("SpreadBuyMax", 0),
                    "on3": buy_points_key.get("SpreadBuyOn3", 0),
                    "off3": buy_points_key.get("SpreadBuyOff3", 0),
                    "on7": buy_points_key.get("SpreadBuyOn7", 0),
                    "off7": buy_points_key.get("SpreadBuyOff7", 0),
                },
                "Total": {
                    "amount": buy_points_key.get("TotalBuy", 0),
                    "max": buy_points_key.get("TotalBuyMax", 0)
                }
            }

        market_data["internal_data"] = league
        return market_data

    def _convert_date(self, start_date: str):
        pst = ZoneInfo("America/Chicago")
        start_date_dt = (
            datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f")
            .replace(tzinfo=pst)
        )

        if start_date_dt.second == 1:
            start_date_dt = start_date_dt.replace(second=0)

        return start_date_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


    def _handle_extraction_odds(self, team: str | None, line_look_up_id: str | None, direction: str | None,
                               market_name: str, odds_look_up_id: str, event_data: dict, league: str, player_name: str | None = None):

        def line_handler():
            if not line_look_up_id:
                return None

            line = event_data.get(line_look_up_id)
            if line is None:
                return None

            # Spread is one shared number, favourite gets the negative side
            if line_look_up_id == "Spread":
                return -abs(float(line)) if team == event_data.get("FavoredTeamID") else abs(float(line))

            return float(line)


        odds = event_data.get(odds_look_up_id)
        if not odds:
            return None

        stats = SportsbookStats(
            league=league,
            market=market_name,
            line=line_handler(),
            bet_player=player_name,
            # line=event_data.get(line_look_up_id) if line_look_up_id else None,
            bet_team=team,
            bet_type=direction,
            future=False,
            odds_format=OddsFormat(american_odds=float(event_data.get(odds_look_up_id))),
        )




        return stats

    def calulate_spread_buy_points(self, spread_line: float | int, spread_odds: float, buy_points: dict,
                                   period_description: str, market_name: str, bet_team: str, league: str) -> list:
        """
        Calculates the new spread line and odds after applying the buy points for spread markets.
        :param spread_line: The original spread line.
        :param spread_odds: The original spread odds.
        :param buy_points: The buy points dict from market_caller, e.g. {"Spread": {"amount": 10, "max": 4, "on3": 25, ...}}.
        :param period_description: The period of the line, buy points only apply to "game".
        :param market_name: The name of the market for which the buy points are being calculated.
        :param bet_team: The team for which the buy points are being calculated.
        """
        spread = buy_points.get("Spread") or {}
        amount = spread.get("amount")
        max_steps = spread.get("max")

        if not amount or not max_steps or period_description.lower() != "game":
            return []

        # (cost to land on, cost to move off), falls back to the normal amount
        key_numbers = {
            3: (spread.get("on3") or amount, spread.get("off3") or amount),
            7: (spread.get("on7") or amount, spread.get("off7") or amount),
        }

        odds_list = []
        current_line = spread_line
        current_odds = spread_odds

        for _ in range(max_steps):
            new_line = current_line + 0.5

            # A step touches 3 or 7 either by leaving it (starts on it) or by
            # reaching it (ends on it). Both are charged the key-number cost.
            # e.g. -3.5 -> -3.0 ends on 3 (on cost), -3.0 -> -2.5 starts on 3 (off cost)
            if abs(current_line) in key_numbers:
                cost = key_numbers[abs(current_line)][1]
            elif abs(new_line) in key_numbers:
                cost = key_numbers[abs(new_line)][0]
            else:
                cost = amount

            current_line = new_line
            current_odds -= cost

            if -100 < current_odds < 100:
                current_odds -= 200

            odds_list.append(SportsbookStats(
                league=league,
                market=market_name,
                bet_team=bet_team,
                line=current_line,
                bet_type=None,
                future=False,
                odds_format=OddsFormat(american_odds=float(current_odds)),
            ))

        return odds_list

    def calulate_total_buy_points(self, total_line: float | int, total_odds: float, buy_points: dict,
                                  period_description: str, market_name: str, direction: str, league: str) -> list:
        """
        Calculates the new total line and odds after applying the buy points for total markets.
        :param total_line: The original total line.
        :param total_odds: The original total odds.
        :param buy_points: The buy points dict from market_caller, e.g. {"Total": {"amount": 10, "max": 4}}.
        :param period_description: The period of the line, buy points only apply to "game".
        :param market_name: The name of the market for which the buy points are being calculated.
        :param direction: "Over" or "Under". Over buys the total down, Under buys it up.
        """
        total = buy_points.get("Total") or {}
        amount = total.get("amount")
        max_steps = total.get("max")

        if not amount or not max_steps or period_description.lower() != "game":
            return []

        # Over wants a lower total, Under wants a higher one
        step_size = -0.5 if direction.lower() == "over" else 0.5

        odds_list = []
        current_line = total_line
        current_odds = total_odds

        for _ in range(max_steps):
            current_line += step_size
            current_odds -= amount

            # American odds jump from +100 straight to -100, so skip the gap
            if -100 < current_odds < 100:
                current_odds -= 200

            odds_list.append(SportsbookStats(
                league=league,
                market=market_name,
                bet_team=None,
                line=float(current_line),
                bet_type=direction,
                future=False,
                odds_format=OddsFormat(american_odds=float(current_odds)),
            ))

        return odds_list

    async def _build_player_markets(self, espn_mapping: dict, event_data: dict, internal_data: dict) -> GameData | None:
        player_name = event_data.get("ShortName1")
        stat_type = event_data.get("ShortName2")

        if not player_name or not stat_type:
            return None

        modified_date = self._convert_date(event_data.get("GameDateTime"))
        league = internal_data.get("mapped_name")

        period = event_data.get("PeriodDescription", '').lower()

        found_team = await self.find_espn_mapping(espn_mapping=espn_mapping, player_name=player_name, league=league, game_date=modified_date)

        if not found_team:
            return None

        team_1 = found_team.get("team")
        team_2 = found_team.get("opponent")

        options = [
            {"market": stat_type, "team": team_1, "line_look_up_id": "TotalPoints", "direction": "Over",
             "odds_look_up_id": "TtlPtsAdj1"},
            {"market": stat_type, "team": team_1, "line_look_up_id": "TotalPoints", "direction": "Under",
             "odds_look_up_id": "TtlPtsAdj2"},
        ]

        game_data = GameData(
            start_date=modified_date,
            league=league,
            team_data=TeamData(team_a=team_1, team_b=team_2),
            game_key_items=[team_1, team_2],
            odds=[],
        )

        odds = []

        for option in options:
            raw_market_name = option.get("market", '')
            market_name = raw_market_name if period == "game" else f"{period} {raw_market_name}"

            stat = self._handle_extraction_odds(
                team=option.get("team"),
                line_look_up_id=option.get("line_look_up_id"),
                direction=option.get("direction"),
                market_name=market_name,
                odds_look_up_id=option.get("odds_look_up_id"),
                event_data=event_data,
                league=league,
                player_name=player_name
            )

            if not stat:
                continue

            odds.append(stat)

        if odds:
            game_data.odds.extend(odds)
            # # print(game_data.odds)
            # from dataclasses import asdict
            # import json
            # print(json.dumps([asdict(odd) for odd in game_data.odds], indent=2))
            return game_data

        return None


    async def _build_main_markets(self, event_data: dict, buy_points: dict, internal_data: dict) -> GameData | None:
        modified_date = self._convert_date(event_data.get("GameDateTime"))
        league = internal_data.get("mapped_name")

        team_1 = event_data.get("Team1ID")
        team_2 = event_data.get("Team2ID")

        period = event_data.get("PeriodDescription", '').lower()

        options = [
            {"market": "MoneyLine1", "team": team_1, "line_look_up_id": None, "direction": None, "odds_look_up_id": "MoneyLine1", "mapped_name": "Moneyline"},
            {"market": "MoneyLine2", "team": team_2, "line_look_up_id": None, "direction": None, "odds_look_up_id": "MoneyLine2", "mapped_name": "Moneyline"},
            {"market": "SpreadAdj1", "team": team_1, "line_look_up_id": "Spread", "direction": None, "odds_look_up_id": "SpreadAdj1",
             "has_buy_points": True, "buy_points_type": "spread", "mapped_name": "Spread"},
            {"market": "SpreadAdj2", "team": team_2, "line_look_up_id": "Spread", "direction": None, "odds_look_up_id": "SpreadAdj2",
             "has_buy_points": True, "buy_points_type": "spread", "mapped_name": "Spread"},
            {"market": "TtlPtsAdj1", "team": None, "line_look_up_id": "TotalPoints", "direction": "Over",
             "odds_look_up_id": "TtlPtsAdj1",
             "has_buy_points": True, "buy_points_type": "total", "mapped_name": "Total"},
            {"market": "TtlPtsAdj2", "team": None, "line_look_up_id": "TotalPoints", "direction": "Under",
             "odds_look_up_id": "TtlPtsAdj2",
             "has_buy_points": True, "buy_points_type": "total", "mapped_name": "Total"},
            {"market": "Team1TtlPtsAdj1", "team": team_1, "line_look_up_id": "Team1TotalPoints", "direction": "Over", "odds_look_up_id": "Team1TtlPtsAdj1", "mapped_name": "Team Total"},
            {"market": "Team1TtlPtsAdj2", "team": team_1, "line_look_up_id": "Team1TotalPoints", "direction": "Under", "odds_look_up_id": "Team1TtlPtsAdj2", "mapped_name": "Team Total"},
            {"market": "Team2TtlPtsAdj1", "team": team_2, "line_look_up_id": "Team2TotalPoints", "direction": "Over", "odds_look_up_id": "Team2TtlPtsAdj1", "mapped_name": "Team Total"},
            {"market": "Team2TtlPtsAdj2", "team": team_1, "line_look_up_id": "Team2TotalPoints", "direction": "Under", "odds_look_up_id": "Team2TtlPtsAdj2", "mapped_name": "Team Total"},

        ]

        game_data = GameData(
            start_date=modified_date,
            league=league,
            team_data=TeamData(team_a=team_1, team_b=team_2),
            game_key_items=[team_1, team_2],
            odds=[],
        )

        odds = []

        for option in options:
            internal_mapped_name = option.get("mapped_name", '').lower()

            mapped_market_name = self._special_mapping(internal_mapped_name, league)

            market_name = mapped_market_name if period == "game" else f"{period} {mapped_market_name}"

            stat = self._handle_extraction_odds(
                team=option.get("team"),
                line_look_up_id=option.get("line_look_up_id"),
                direction=option.get("direction"),
                market_name=market_name,
                odds_look_up_id=option.get("odds_look_up_id"),
                event_data=event_data,
                league=league
            )

            if not stat:
                continue

            if option.get("has_buy_points") and option.get("buy_points_type") == "spread":
                game_data.odds.extend(self.calulate_spread_buy_points(
                    spread_line=stat.line,
                    spread_odds=stat.odds_format.get("american_odds"),
                    buy_points=buy_points,
                    period_description=event_data.get("PeriodDescription", ''),
                    market_name=stat.market,
                    bet_team=stat.bet_team,
                    league=league
                ))
            elif option.get("buy_points_type") == "total":
                game_data.odds.extend(self.calulate_total_buy_points(
                    total_line=stat.line,
                    total_odds=stat.odds_format.get("american_odds"),
                    buy_points=buy_points,
                    period_description=event_data.get("PeriodDescription", ''),
                    market_name=stat.market,
                    direction=stat.bet_type,
                    league=league
                ))


            odds.append(stat)

        if odds:
            game_data.odds.extend(odds)
            # # print(game_data.odds)
            # from dataclasses import asdict
            # import json
            # print(json.dumps([asdict(odd) for odd in game_data.odds], indent=2))
            return game_data

        return None


    async def run_book(self) -> list | None:
        username = os.getenv("BUCKEYE_2_USERNAME")

        if not username:
            raise ValueError("Missing required environment variable: BUCKEYE_2_USERNAME")

        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            auth_token = await self.auth_redis_manager.get_data(self.auth_id_name)

            if not auth_token:
                return None

            raw_leagues = await self.api_caller(
                url=self.book_data.url.get("leagues"),
                method=self.book_data.method,
                use_proxy=True,
                headers={
                    **self.book_data.headers,
                    "Authorization": f"Bearer {auth_token}"
                },

                data=urlencode({
                    "customerID": f"{username}_0",
                    "wagerType": "Straight",
                    "office": "WAGERHOME",
                    "placeLateFlag": "false",
                    "operation": "Get_SportsLeagues",
                    "RRO": 1,
                    "agentSite": 0
                })
            )

            leagues = self._filter_leagues(raw_leagues.get("Leagues", []))
            markets = [
                self.market_caller(
                    username=username,
                    auth_token=auth_token,
                    league=league
                )

                for league in leagues
            ]

            market_results = await asyncio.gather(*markets)

            event_data = {}

            espn_mapping = await self._load_espn_mapping()

            for market in market_results:
                lines = market.get("Lines", [])
                if not market or not lines:
                    continue

                internal_data = market.get("internal_data")
                buy_points = market.get("buypoints", {})


                if internal_data.get("game_type") == "game":
                    game_data_list = await asyncio.gather(*[
                        self._build_main_markets(
                            event_data=line,
                            internal_data=internal_data,
                            buy_points=buy_points
                        )
                        for line in lines
                    ])
                else:
                    if not espn_mapping:
                        continue

                    game_data_list = await asyncio.gather(*[
                        self._build_player_markets(
                            event_data=line,
                            internal_data=internal_data,
                            espn_mapping=espn_mapping
                        )
                        for line in lines
                    ])


                for game_data in game_data_list:
                    if game_data:
                        self.add_to_events(event_data, game_data, GameData)


            buckeye_2_data = list(event_data.values())

            await self.store_data(
                data_to_store=buckeye_2_data,
                key_name=self.book_data.name,
                wrapped_data=True,
            )

            await self.flush_unmapped()
            return buckeye_2_data


if __name__ == "__main__":
    metallic = Buckeye2()
    asyncio.run(metallic.run_book())


