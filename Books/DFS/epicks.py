import asyncio
import aiohttp
from Books.Bases.dfs_book_base import DFSBookBase
from Monitoring.monitoring import create_sentry_message
from Settings.Models.dfs_models import DFSStats
from Settings.Models.base_models import GameData, TeamData, OddsFormat
from Utils.request_caller import SportbookRequestType


class Epicks(DFSBookBase):
    def __init__(self):
        super().__init__(book_name="epicks", request_type=SportbookRequestType.ASYNC)

    def _extract_leagues(self, league_data: dict) -> set:
        return set(
            league
            for league, additional_info in league_data.items()\
            if additional_info.get("status") == "ACTIVE"
        )

    async def _get_league_data(self, league: str, session: aiohttp.ClientSession) -> list:
        """Get raw league data from the API, handling pagination if necessary."""
        league_data = []

        # Recursive function to handle pagination
        async def _pagination_runner(cursor_payload: dict | None = None):
            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url").format(league=league),
                method="POST",
                payload=cursor_payload if cursor_payload else {}
            )

            if not api_data:
                return None

            raw_data = {
                "projections": api_data.get("projections", {}),
                "events": api_data.get("events", {}),
                "props": api_data.get("props", {}),
                "teams": api_data.get("teams", {}),
                "players": api_data.get("players", {}),
            }

            league_data.append(raw_data)

            if api_data.get("next_cursor"):
                await _pagination_runner(
                    cursor_payload={
                        "cursor": api_data.get("next_cursor")
                    }
                )

        await _pagination_runner()

        return league_data

    def _extract_team_data(self, teams: dict, events: dict, event_id: str | int, players: dict, player_id: str | int,
                           start_date: str) -> dict:
        """Extract team data"""
        raw_home_team = events.get(event_id, {}).get("team_home")
        raw_away_team = events.get(event_id, {}).get("team_away")

        home_team = teams.get(raw_home_team, {}).get("name_std")
        home_abbreviation = teams.get(raw_home_team, {}).get("name_abbr", None)
        away_team = teams.get(raw_away_team, {}).get("name_std")
        away_abbreviation = teams.get(raw_away_team, {}).get("name_abbr", None)

        player_info = players.get(player_id, {})
        player_team = player_info.get("team_name")

        if home_team and away_team:
            team_key = Epicks.generate_key([home_team, away_team, start_date])
        else:
            team_key = Epicks.generate_key([player_team, start_date])

        return {
            "team_a": home_team,
            "team_a_abbreviation": home_abbreviation,
            "team_b": away_team,
            "team_b_abbreviation": away_abbreviation,
            "player_team": player_team,
            "team_key": team_key,
        }

    def _extract_data(self, projections: dict, teams: dict, events: dict, players: dict, props: dict) -> GameData | None:
        event_id = projections.get("event_id")
        player_id = projections.get("subject_id")
        start_date = projections.get("iso_event_datetime")

        team_data = self._extract_team_data(
            teams=teams,
            events=events,
            event_id=event_id,
            players=players,
            player_id=player_id,
            start_date=start_date
        )

        direction_list = [
            val
            for key, val in {
                "odds_over": "over",
                "odds_under": "under"
            }.items()
            if projections.get(key)
        ]

        stat_info = props.get(projections.get("prop"), {})
        if not stat_info:
            return None

        stat_type = stat_info.get("name_std").lower()


        return GameData(
            league=projections.get("league").lower(),
            game_key=team_data.get("team_key"),
            start_date=start_date,
            team_data=TeamData(
                team_a=team_data.get("team_a"),
                team_a_abbreviation=team_data.get("team_a_abbreviation"),
                team_b=team_data.get("team_b"),
                team_b_abbreviation=team_data.get("team_b_abbreviation"),
            ),
            odds=[
                DFSStats(
                    player_name=projections.get("subject_std"),
                    player_team=team_data.get("player_team"),
                    stat_type=stat_type,
                    future=False,
                    combo=True if projections.get("is_combo") else False,
                    line=projections.get("line_value"),
                    bet_type=direction,
                    regular_line=True if not projections.get("is_promo") else False,
                    discounts={
                        "discount_name": "Promo",
                    } if projections.get("is_promo") else {},
                    odds_format=OddsFormat(
                        american_odds=float(projections.get(f"odds_{direction}")),
                    )
                )
                for direction in direction_list
            ],
            solo_game=False if all([team_data.get("team_a"), team_data.get("team_b")]) else True,
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("league_url"),
                method=self.book_data.method,
            )

            if not league_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No leagues returned",
                    level="error"
                )

                return

            leagues = self._extract_leagues(league_data)

            tasks = [
                self._get_league_data(league, session)
                for league in leagues
            ]

            data = await asyncio.gather(*tasks)
            combined_data = [item for sublist in data for item in sublist if item] # Flatten the list and remove None entries

            if not combined_data:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="api_failure",
                    message="No league data returned",
                    level="error"
                )
                return

            events_dict = {}
            for raw_data in combined_data:
                projections = raw_data.get("projections", {})
                events = raw_data.get("events", {})
                props = raw_data.get("props", {})
                teams = raw_data.get("teams", {})
                players = raw_data.get("players", {})

                for projection_key, projection_details in projections.items():
                    player_data = self._extract_data(projection_details, teams=teams, events=events, players=players, props=props)
                    if player_data:
                        self.add_to_events(events_dict, player_data, GameData)

            epicks_data = list(events_dict.values())

            mapped_data = await self.external_mapper(epicks_data)

            await self.store_data(
                database=self.redis_database,
                data_to_store=mapped_data,
                book_name=self.book_data.name
            )

            return mapped_data