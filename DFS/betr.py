import asyncio
import aiohttp
from Mapper.static_mapper import STAT_TYPES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, Stats, TeamData, OptionalStatInformation

class Betr(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="betr")


    @staticmethod
    def _extract_leagues(api_data):
        """ Extract the leagues from the API data."""
        return set(
            league.get("id")
            for league in api_data.get("data").get("getUpcomingEventsV2", [])
        )

    async def _extract_game_data(self, league, session):
        payload = {
                "operationName": "EventsInfo",
                "query": """
                query EventsInfo($ids: [String!]!) {
                  getEventsByIdsV2(ids: $ids) {
                    ...EventInfoData
                    ... on TeamTournamentEvent {
                      teams {
                        ...TeamInfoWithPlayers
                        __typename
                      }
                      __typename
                    }
                    ... on TeamVersusEvent {
                      teams {
                        name
                        ...TeamInfoWithPlayers
                        __typename
                      }
                      __typename
                    }
                    ... on IndividualTournamentEvent {
                      players {
                        ...PlayerInfoWithProjections
                        __typename
                      }
                      __typename
                    }
                    ... on IndividualVersusEvent {
                      players {
                        ...PlayerInfoWithProjections
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                }
                fragment EventInfoData on EventV2 {
                  date
                  status
                  sport
                  playerStructure
                  league
                  attributes {
                    key
                    value
                    __typename
                  }
                  name
                  dedicated
                  __typename
                }
                fragment TeamInfoWithPlayers on Team {
                  ...TeamInfo
                  players {
                    ...PlayerInfoWithProjections
                    __typename
                  }
                  __typename
                }
                fragment TeamInfo on Team {
                  id
                  name
                  league
                  sport
                  color
                  secondaryColor
                  largeIcon
                  __typename
                }
                fragment PlayerInfoWithProjections on Player {
                  ...PlayerInfo
                  projections {
                    ...PlayerProjection
                    __typename
                  }
                  __typename
                }
                fragment PlayerInfo on Player {
                  id
                  firstName
                  lastName
                  attributes {
                    key
                    value
                    __typename
                  }
                  __typename
                }
                fragment PlayerProjection on Projection {
                  marketStatus
                  isLive
                  type
                  label
                  name
                  key
                  order
                  value
                  nonRegularPercentage
                  nonRegularValue
                  allowedOptions {
                    outcome
                    __typename
                  }
                  currentValue
                  __typename
                }
            """,
                "variables": {"ids": list(league)},
            }

        raw_game_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
                payload=payload
            )

        game_data = self.check_api_response(sportsbook="betr", results=raw_game_data)
        if not game_data:
            return

        return [
            self._game_info_controller(game)
            for game in game_data.get("data", {}).get("getEventsByIdsV2", [])
        ]

    def _extract_teams(self, data, player_name=None):
        # Extract team names and generate a unique key for the match up

        if data.get("playerStructure") == "TEAM":
            team_a, team_b = data.get("name").split("@")
            team_a = self.clean_and_normalize_name(team_a.strip())
            team_b = self.clean_and_normalize_name(team_b.strip())
            team_key = self._generate_key([team_a, team_b, self.cache_time(data.get("date"))])

            return {
                "team_a": team_a,
                "team_b": team_b,
                "team_key": team_key,
            }

        # Solo games won't have team names, so we use the player's name and date to generate a key.
        team_key = self._generate_key([player_name, self.cache_time(data.get("date"))])
        return {
            "team_a": player_name,
            "team_b": None,
            "team_key": team_key,
        }


    def _extract_projections(self, players, player_team_name, league, game_date, team_names=None, solo_game=False,):
        def stat_type_helper(stat_types):
            """Conflict with other books on some stat types, so we need to manually adjust them here."""
            if stat_types.lower() == "strikeouts":
                stat_types = "batter strikeouts"

            return STAT_TYPES.get(stat_types.lower(), stat_types.title())

        option_mapper = {
            "more": "over",
            "less": "under",
        }

        results = []


        # Iterate through player list.
        for player in players:
            stats = []
            player_name = self.clean_and_normalize_name(f"{player.get('firstName')} {player.get('lastName')}")

            # player_team = player.get("name") if not solo_game else player_name
            player_team = player_team_name if not solo_game else player_name

            # If it's a solo game, we extract team names based on the player name.
            if solo_game:
                team_names = self._extract_teams(player, player_name)


            # Extract all the stats for the player.
            for projection in player.get("projections", []):
                bet_options = [
                    Stats(
                        stat_type=stat_type_helper(projection.get("label")),
                        line=projection.get("value") if projection.get("type") == "REGULAR" else projection.get("nonRegularValue"),
                        bet_direction=option_mapper.get(options.get("outcome").lower(), options.get("outcome").title()),
                        regular_line=True if projection.get("type").lower() == "regular" else False,
                        optional_stats=OptionalStatInformation(
                            odds_type="standard" if projection.get("type") == "Regular" else projection.get("type").replace(
                                "_", " ").lower(),
                            market_type="full",
                        )
                    )
                    for options in projection.get("allowedOptions")
                ]

                stats.extend(bet_options)

            results.append(
                PlayerData(
                    player_name=self.clean_and_normalize_name(player_name).strip(),
                    league=league,
                    start_date=game_date,
                    team_data=TeamData(
                        team_a=team_names.get("team_a"),
                        team_b=team_names.get("team_b"),
                        team_key=team_names.get("team_key"),
                        player_team=self.clean_and_normalize_name(player_team),
                    ),
                    future=False,
                    stats=stats,
                    solo_game=solo_game
                )
            )

        return results

    def _extract_team_games(self, teams, team_names, league, game_date):
        if not teams:
            self._api_call_log(sportsbook="betr", error_details="No teams found in team game extraction.")
            return []

        return [
            item
            for team in teams
            for item in self._extract_projections(
                players=team.get("players", []),
                player_team_name=team.get("name", ""),
                league=league,
                game_date=game_date,
                team_names=team_names
            )
        ]

    def _extract_solo_games(self, players):
        if not players:
            self._api_call_log(sportsbook="betr", error_details="No players found in solo game extraction.")
            return []

    def _game_info_controller(self, game):
        results = []
        if game.get("status") != "SCHEDULED":
            return

        league = self.LEAGUE_MAPPING.get(game.get("league").lower(), game.get("league"))
        game_date = self.cache_time(game.get("date"))


        # Conditional check as Solo and Team games have a different structure.
        if game.get("playerStructure") == "INDIVIDUAL":
            results.extend(
                self._extract_projections(game.get("players", []), game.get("name", ""), league, game_date, solo_game=True)
            )
        elif game.get("playerStructure") == "TEAM":
            team_names = self._extract_teams(game)
            game_data = self._extract_team_games(game.get("teams"), team_names, league, game_date)
            results.extend(game_data)
        else:
            self._api_call_log(sportsbook="betr", error_details=f"Unknown player structure: {game.get('playerStructure')}")
            return

        if not results:
            return


        return results

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            raw_api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                payload={
                    "operationName": "AllLeaguesUpcomingEvents",
                    "query": """query AllLeaguesUpcomingEvents {
                              getUpcomingEventsV2 {
                                id
                                league
                              }
                            }""",
                }
            )

            api_data = self.check_api_response(sportsbook="betr", results=raw_api_data)
            if not api_data:
                return

            leagues = self._extract_leagues(api_data)
            betr_data = await self._extract_game_data(leagues, session)

            if not betr_data:
                return

            # Flatten the list of lists into a single list of games.
            results = [game for league_results in betr_data if league_results for game in league_results]
            return await self._database_mapper(results)

if __name__ == "__main__":
    betr = Betr()
    asyncio.run(betr.run_book())