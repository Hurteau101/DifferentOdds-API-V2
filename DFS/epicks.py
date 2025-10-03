import aiohttp
import asyncio

from Mapper.static_mapper import LEAGUES, STAT_TYPES
from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import PlayerData, TeamData, Stats


class Epicks(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="epicks")

    def _extract_leagues(self, league_data):
        return set(
            league
            for league, additional_info in league_data.items()\
            if additional_info.get("status") == "ACTIVE"
        )

    async def _get_league_data(self, league, session):
        """Get raw league data from the API, handling pagination if necessary."""
        league_data = []

        # Recursive function to handle pagination
        async def _pagination_runner(cursor_payload=None):
            api_data = await self.api_caller(
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

    def _extract_team_data(self, teams, events, event_id, players, player_id, start_date):
        """Extract team data"""
        raw_home_team = events.get(event_id, {}).get("team_home")
        raw_away_team = events.get(event_id, {}).get("team_away")

        home_team = self.clean_and_normalize_name(teams.get(raw_home_team, {}).get("name_std"))
        home_abbreviation = teams.get(raw_home_team, {}).get("name_abbr", None)
        away_team = self.clean_and_normalize_name(teams.get(raw_away_team, {}).get("name_std"))
        away_abbreviation = teams.get(raw_away_team, {}).get("name_abbr", None)

        player_info = players.get(player_id, {})
        player_team = self.clean_and_normalize_name(player_info.get("team_name"))

        if home_team and away_team:
            team_key = self._generate_key([home_team, away_team, start_date])
        else:
            team_key = self._generate_key([player_team, start_date])

        return {
            "team_a": home_team,
            "team_a_abbreviation": home_abbreviation,
            "team_b": away_team,
            "team_b_abbreviation": away_abbreviation,
            "player_team": player_team,
            "team_key": team_key,
        }

    def _extract_data(self, projections, teams, events, players, props):
        # raw_data = {
        #     "projections": api_data.get("projections", {}),
        #     "events": api_data.get("events", {}),
        #     "props": api_data.get("props", {}),
        #     "teams": api_data.get("teams", {}),
        # }

        event_id = projections.get("event_id")
        player_id = projections.get("subject_id")
        start_date = self.cache_time(projections.get("iso_event_datetime"))

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


        return PlayerData(
            player_name=projections.get("subject_std"),
            league=LEAGUES.get(projections.get("league").lower(), projections.get("league").upper()),
            start_date=start_date,
            team_data=TeamData(
                team_a=team_data.get("team_a"),
                team_a_abbreviation=team_data.get("team_a_abbreviation"),
                team_b=team_data.get("team_b"),
                team_b_abbreviation=team_data.get("team_b_abbreviation"),
                player_team=team_data.get("player_team"),
                team_key=team_data.get("team_key")
            ),
            future=False,
            stats=[
                Stats(
                    stat_type=STAT_TYPES.get(stat_type, stat_type.title()),
                    line=projections.get("line_value"),
                    bet_direction=direction,
                    regular_line=True if not projections.get("is_promo") else False,
                    discounts={
                        "discount_name": "Promo",
                    } if projections.get("is_promo") else {},
                    optional_stats={
                        "odds": {
                            "american_odds": projections.get(f"odds_{direction}"),
                        }
                    }
                )
                for direction in direction_list
            ],
            solo_game=False if all([team_data.get("team_a"), team_data.get("team_b")]) else True,
            combo=True if projections.get("is_combo") else False,
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            league_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("league_url"),
                method=self.book_data.method,
            )

            if not league_data:
                self.file_logger.log(
                    message="Couldn't map leagues for Epicks",
                )
                return None

            leagues = self._extract_leagues(league_data)

            tasks = [
                self._get_league_data(league, session)
                for league in leagues
            ]

            data = await asyncio.gather(*tasks)
            combined_data = [item for sublist in data for item in sublist if item] # Flatten the list and remove None entries
            import json
            with open("epicks_raw.json", "w") as f:
                json.dump(combined_data, f, indent=2)


            player_data_list = {}
            for raw_data in combined_data:
                projections = raw_data.get("projections", {})
                events = raw_data.get("events", {})
                props = raw_data.get("props", {})
                teams = raw_data.get("teams", {})
                players = raw_data.get("players", {})

                for projection_key, projection_details in projections.items():
                    player_data = self._extract_data(projection_details, teams=teams, events=events, players=players, props=props)
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

            epicks_data = list(player_data_list.values())
            return await self._database_mapper(epicks_data)


if __name__ == "__main__":
    epicks = Epicks()
    asyncio.run(epicks.run_book())