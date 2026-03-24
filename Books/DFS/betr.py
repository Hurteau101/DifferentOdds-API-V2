import asyncio

import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType
from Settings.Models.dfs_models import DFSStats, OptionalStatInformation
from Settings.Models.base_models import GameData, TeamData, get_static_mapping

class Betr(DFSBookBase):
    def __init__(self):
        super().__init__(request_type=SportbookRequestType.ASYNC, book_name="betr")

    @staticmethod
    def _extract_leagues(api_data: dict) -> set:
        """ Extract the leagues from the API data."""
        return set(
            league.get("id")
            for league in api_data.get("data", {}).get("getUpcomingEventsV2", [])
        )

    async def _extract_game_data(self, league: set, session: aiohttp.ClientSession) -> list | None:
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

        game_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers=self.book_data.headers,
                payload=payload
            )

        if not game_data:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="api_failure",
                message="No Game Data Found",
                level="error"
            )

            return None

        return [
            self._game_info_controller(game)
            for game in game_data.get("data", {}).get("getEventsByIdsV2", [])
        ]

    def _extract_teams(self, data: dict, player_name: str = None) -> dict:
        # Extract team names and generate a unique key for the match up

        if data.get("playerStructure") == "TEAM":
            team_a, team_b = data.get("name").split("@")
            team_a = team_a.strip()
            team_b = team_b.strip()
            team_key = Betr.generate_key([team_a, team_b, data.get("date")])

            return {
                "team_a": team_a,
                "team_b": team_b,
                "team_key": team_key,
            }

        # Solo games won't have team names, so we use the player's name and date to generate a key.
        team_key = Betr.generate_key([player_name, data.get("date")])
        return {
            "team_a": player_name,
            "team_b": None,
            "team_key": team_key,
        }


    def _extract_projections(self, players: list, player_team_name: str, league: str, game_date: str,
                             team_names : str | None = None, solo_game: bool = False) -> list:
        def stat_type_helper(stat_types: str) -> str:
            """Conflict with other books on some stat types, so we need to manually adjust them here."""
            if stat_types.lower() == "strikeouts":
                stat_types = "batter strikeouts"

            return stat_types.lower()

        option_mapper = {
            "more": "over",
            "less": "under",
        }

        results = []

        # Iterate through player list.
        for player in players:
            stats = []
            player_name = f"{player.get('firstName')} {player.get('lastName')}"

            # player_team = player.get("name") if not solo_game else player_name
            player_team = player_team_name if not solo_game else player_name

            # If it's a solo game, we extract team names based on the player name.
            if solo_game:
                team_names = self._extract_teams(player, player_name)

            # Extract all the stats for the player.
            for projection in player.get("projections", []):
                if league.upper() in self.esport_leagues and projection.get("type") != "REGULAR":
                    continue

                bet_options = [
                    DFSStats(
                        player_name=player_name,
                        player_team=player_team,
                        stat_type=stat_type_helper(projection.get("label")),
                        future=False,
                        line=projection.get("value") if projection.get("type") == "REGULAR" else projection.get("nonRegularValue"),
                        bet_type=option_mapper.get(options.get("outcome").lower(), options.get("outcome").title()),
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
                GameData(
                    league=league,
                    game_key=team_names.get("team_key"),
                    start_date=game_date,
                    team_data=TeamData(
                        team_a=team_names.get("team_a"),
                        team_b=team_names.get("team_b"),
                    ),
                    odds=stats,
                    solo_game=solo_game
                )
            )

        return results

    def _extract_team_games(self, teams: list, team_names: dict | str, league: str, game_date: str) -> list:
        if not teams:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="team_failure",
                message="No teams found in team game extraction.",
                level="error"
            )
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

    def _extract_solo_games(self, players: list) -> list | None:
        if not players:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="solo_game_failure",
                message="No players found in solo game extraction.",
                level="error"
            )

            return []

    def _game_info_controller(self, game: dict) -> list | None:
        results = []
        if game.get("status") != "SCHEDULED":
            return None

        # Import here and in Dataclass as this does require the leagues to be mapped prior dataclass creation.
        static_mapping = get_static_mapping().get("leagues", {}) or {}

        league = static_mapping.get(game.get("league").lower(), {}).get("mapped_name", game.get("league").upper())

        game_date = game.get("date")

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
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="unknown_player_structure",
                message=F"Unknown player structure encountered in game data [{game.get('playerStructure')}].",
                level="error"
            )

            return None

        return results

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                book_name=self.book_data.name,
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

            if not api_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data found from API.",
                    level="error"
                )

                return

            leagues = self._extract_leagues(api_data)

            betr_data = await self._extract_game_data(leagues, session)

            if not betr_data:
                return

            events = {}
            for games in betr_data:
                for game_data in games:
                    if game_data:
                        self.add_to_events(events, game_data, GameData)


            betr_data = list(events.values())

            mapped_data = await self.map_runner(session=session, sportsbook_data=betr_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data

if __name__ == "__main__":
    betr = Betr()
    asyncio.run(betr.run_book())