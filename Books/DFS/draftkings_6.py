import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData
from Utils.request_caller import SportbookRequestType


class DraftKingsPickSix(DFSBookBase):
    MARKET_MAPPING = {
        "1": "over",
        "2": "under",
    }

    def __init__(self):
        super().__init__(book_name="draftkings_6", request_type=SportbookRequestType.ASYNC)

    def _extract_league_keys(self, api_data: dict) -> list:
        return [
            data.get("sportLeagueKey")
            for data in api_data.get("sportLeagues", [])
            if data.get("hasPicksAvailable")
        ]

    def fetch_market(self, market_data: dict, team_mapping: dict, league_id: int):
        def format_team(team: dict):
            if not team:
                return None

            if not team.get("city"):
                return team.get("name")

            return f"{team.get('city')} {team.get('name')}"


        player_names_dict = market_data.get("entityInfoByDkId", {})
        pick_category_dict = market_data.get("pickSixMarketById", {})

        game_data_dict = market_data.get("competitionById", {})

        market_dict = {}

        for pickable in market_data.get("pickCardByPickableId").values():
            entity = next((
                entity
                for entity in pickable.get("entities", [])
            ), None)

            if not entity:
                continue

            game_id = next((
                int(ent)
                for ent in entity.get("compIds")
            ), 0)

            game_found = team_mapping.get(game_id, {})
            if not game_found:
                continue


            player_name = player_names_dict.get(str(entity.get("dkId")), {}).get("fullName")
            game_name = game_data_dict.get(str(game_id), {}).get("name")

            game_bucket = market_dict.setdefault(game_name, {})

            for market in pickable.get("activePickableMarkets", []):
                if market.get("isPaused"):
                    continue

                found_market = pick_category_dict.get(str(market.get("pickSixMarketId")), {})
                if not found_market:
                    continue

                player_team_id = game_data_dict.get(str(game_id), {}).get("entityCompByDkId", {}).get(str(entity.get("dkId"))).get("teamId")

                player_team = next(
                    (
                        format_team(team)
                        for team in [game_found.get("homeTeam", {}), game_found.get("awayTeam", {})]
                        if team and str(team.get("teamId")) == str(player_team_id)
                    ),
                    None
                )

                for selection in market.get("activeSelections", []):
                    if selection.get("isLive"):
                        continue

                    team_a = format_team(game_found.get("homeTeam", {}))
                    team_b = format_team(game_found.get("awayTeam", {}))
                    start_date = game_found.get("startTime")

                    if "." in start_date:
                        start_date = start_date.split(".")[0]


                    if team_a and team_b:
                        game_key = self.generate_key([team_a, team_b, start_date])
                    else:
                        game_key = self.generate_key([player_name, start_date])

                    league = game_found.get("leagueAbbreviation") or game_found.get("leagueName")


                    game_bucket.update({
                        "team_a": team_a,
                        "team_b": team_b,
                        "team_a_abbreviation": game_found.get("homeTeam", {}).get("abbreviation") if team_a else None,
                        "team_b_abbreviation": game_found.get("awayTeam", {}).get("abbreviation") if team_b else None,
                        "league": league,
                        "start_date": start_date,
                        "game_key": game_key,
                    })


                    is_regular_line = True if selection.get("standingsMultiplier") == 1 else False

                    stats = game_bucket.setdefault("stats", [])
                    if found_market.get("name") == "Pts + Rebs + Asts":
                        print(pick_category_dict.get(str(market.get("pickSixMarketId")), {}))


                    stats.append({
                        "player_name": player_name,
                        "player_team": player_team,
                        "stat_type": found_market.get("name"),
                        "line": market.get("targetValue"),
                        "direction": self.MARKET_MAPPING.get(str(selection.get("statLinePropositionId"))),
                        "multiplier": selection.get("standingsMultiplier"),
                        "regular_line": is_regular_line,
                        "odds_type": "standard" if is_regular_line else (
                            "payout boost" if selection.get("standingsMultiplier") > 1 else "payout reduced"
                        ),
                        "betlink": self._generate_bet_link(league=game_found.get("leagueAbbreviation"),
                                                           groupId=str(league_id),
                                                           pickableId=str(selection.get("pickableMarketSelectionId")),
                                                           direction=self.MARKET_MAPPING.get(str(selection.get("statLinePropositionId"))))
                    })

        return market_dict



    async def _extract_game_data(self, league_id: int | str, mapping_data: dict, results: dict, session: aiohttp.ClientSession):
        markets_ids = results.get("pickCategoryById", {}).keys()

        raw_market_data = await asyncio.gather(*[
            self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("individual_market_url").format(league_id=league_id),
                method="get",
                headers=self.book_data.headers,
                params={
                    "pickCategoryId": market_id,
                    "appname": "psxandroid",
                    "version": "260861600",
                    "format": "json"
                }
            )
            for market_id in markets_ids
        ])

        market_data = {}

        for data in raw_market_data:
            fetched = self.fetch_market(market_data=data, team_mapping=mapping_data, league_id=league_id)

            for game, markets in fetched.items():
                if not markets:
                    continue

                if game not in market_data:
                    market_data[game] = GameData(
                        league=markets.get("league"),
                        start_date=markets.get("start_date"),
                        solo_game=False,
                        game_key=markets.get("game_key"),
                        team_data=TeamData(
                            team_a=markets.get("team_a"),
                            team_a_abbreviation=markets.get("team_a_abbreviation"),
                            team_b=markets.get("team_b"),
                            team_b_abbreviation=markets.get("team_b_abbreviation"),
                        ),
                        odds=[]
                    )

                market_data[game].odds.extend(
                    DFSStats(
                        player_name=stat["player_name"],
                        player_team=stat["player_team"],
                        stat_type=stat["stat_type"],
                        line=stat["line"],
                        bet_type=stat["direction"],
                        future=False,
                        regular_line=stat["regular_line"],
                        optional_stats=OptionalStatInformation(
                            multiplier=stat["multiplier"],
                            odds_type=stat["odds_type"],
                            betlink=stat["betlink"]
                        )
                    )
                    for stat in markets.get("stats", [])
                )


        return market_data.values()

    def _generate_bet_link(self, league: str, groupId: str, pickableId: str, direction: str) -> dict:
        mapper = {
            "over": "1",
            "under": "2"
        }

        base = "https://pick6.draftkings.com/?"
        sport = f"sport={league}&"
        pickGroup= f"pickGroup={groupId}&"
        pickable = f"picks={pickableId}%2B{mapper.get(direction)}"
        end = "&entrySource=shareLink"
        url = f"{base}{sport}{pickGroup}{pickable}{end}"

        single_url = f"{base}{sport}{pickGroup}{pickable}{end}"
        starter = f"{base}{sport}{pickGroup}{pickable}"
        middle_adder = f"{pickableId}%2B{mapper.get(direction)}%2C"
        end_adder = f"{pickableId}%2B{mapper.get(direction)}"


        return {
            "pickableId": pickableId,
            "groupId": groupId,
            "base": base,
            "sport": league,
            "side": direction,
            "url": url,
            "link_helper": {
                "single_url": single_url,
                "starter": starter,
                "middle_adder": middle_adder,
                "end_adder": end_adder,
                "end": end,
            }
        }

    async def _get_team_game_ids(self, league_results: list) -> dict:
        team_mapping = {}

        for result in league_results:
            if not result:
                continue

            group_id = result.get("mainPickGroupId", {})
            team_mapping.setdefault(group_id, {})

            group_bucket = team_mapping.setdefault(group_id, {})

            league = next((
                league
                for pick in result.get("pickGroups", [])
                for league in pick.get("leagues", [])
            ), None)

            if not league:
                continue

            for competition in result.get("competitions", []):
                team_bucket = group_bucket.setdefault(competition.get("competitionId"), {})
                team_bucket.update({
                    **league,
                    "homeTeam": competition.get("homeTeam"),
                    "awayTeam": competition.get("awayTeam"),
                    "matchup": competition.get("matchupDisplay"),
                    "startTime": competition.get("startTime"),
                })

        return team_mapping

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_league_keys = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_list_url"),
                method="get",
                headers=self.book_data.headers,
            )

            if not api_league_keys:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league keys returned",
                    level="error"
                )
                return

            league_keys = self._extract_league_keys(api_league_keys)

            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("league_data_url").format(league_key=league_key),
                    method="get",
                    headers=self.book_data.headers,
                    params={
                        "pillIdentifier": league_key,
                        "appname": "psxandroid",
                        "version": "260861600",
                        "format": "json"
                    }
                )

                for league_key in league_keys
            ]

            league_results = await asyncio.gather(*tasks)

            if not league_results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            team_mapping = await self._get_team_game_ids(league_results=league_results)

            league_ids = list(team_mapping.keys())


            tasks = [
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.url.get("main_market_url").format(league_id=league_id),
                    method="get",
                    headers=self.book_data.headers,
                    params={
                        "appname": "psxandroid",
                        "version": "260861600",
                        "format": "json",
                    }
                )

                for league_id in league_ids
            ]

            market_results = await asyncio.gather(*tasks)


            if not market_results:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No market data returned",
                    level="error"
                )
                return

            picksix_data = []

            for league_id, market in zip(league_ids, market_results):
                mapped_data = team_mapping.get(league_id)
                data = await self._extract_game_data(league_id=league_id, mapping_data=mapped_data, results=market, session=session)
                if data:
                    picksix_data.extend(data)

            # from dataclasses import asdict
            # serialize = [asdict(data) for data in picksix_data]


            mapped_data = await self.map_runner(session=session, sportsbook_data=picksix_data)


            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data

if __name__ == "__main__":
    ud = DraftKingsPickSix()
    asyncio.run(ud.run_book())