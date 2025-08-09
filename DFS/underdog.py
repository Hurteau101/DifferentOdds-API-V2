import asyncio
import json

import aiohttp
from Settings.book_base import BookBase, SportbookRequestType
from Settings.dfs_book_base import DFSBookBase
from Settings.dfs_model import *
import re

class Underdog(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="underdog")

    @staticmethod
    def _mapper(api_data):
        """Map the different sections of the API data to their respective dictionaries."""
        team_games = {game.get("id"): game for game in api_data.get("games", [])}
        solo_games = {game.get("id"): game for game in api_data.get("solo_games", [])}
        players = {player.get("id"): player for player in api_data.get("players", [])}
        lines = {line.get("over_under", {}).get("appearance_stat", {}).get("appearance_id"): line for line in
                 api_data.get("over_under_lines", [])}
        return {
            "team_games": team_games,
            "solo_games": solo_games,
            "players": players,
            "lines": lines
        }

    @staticmethod
    def _extract_player_info(player_section):
        """Extract Player Details"""
        league = player_section.get("sport_id")
        first_name = player_section.get("first_name")
        # Have this in here as the league will be esports if this isn't added. Since they add first name as league.
        if first_name is not None and ":" in first_name:
            league = first_name.split(":")[0].strip()
            first_name = None
        last_name = player_section.get("last_name")

        full_name = f"{first_name} {last_name}" if first_name is not None else last_name

        return {
            "player_name": full_name.strip(),
            "league": league.upper(),
            "team_id": player_section.get("team_id"),
            "image": player_section.get("image_url"),
        }

    @staticmethod
    def _extract_team_games(game_section, team_id, player_name):
        """Extract Team Game Details"""
        game_title = game_section.get("full_team_names_title").replace(".", "")
        abbreviation_split = BookBase._split_teams(game_section.get("abbreviated_title").replace(".", ""))

        valid_split = BookBase._split_teams(game_title.replace(".", ""))
        if valid_split:
            team_a, team_b, operator = valid_split["team_a"], valid_split["team_b"], valid_split["operator"].replace(".", "")
            title_split = game_title.split(operator)

            if operator == "@" and team_id == game_section.get("home_team_id"):
                player_team = title_split[1].strip()
            else:
                player_team = title_split[0].strip()

            if operator == "vs" and team_id == game_section.get("home_team_id"):
                player_team = title_split[0].strip()
            else:
                player_team = title_split[1].strip()


            if team_a or team_b is None:
                game_key = BookBase._generate_key([player_name, game_section.get("scheduled_at")])
            else:
                game_key = BookBase._generate_key([team_a, team_b, game_section.get("scheduled_at")])


            return {
                "match_title": game_section.get("full_team_names_title").strip(),
                "player_team": DFSBookBase.clean_and_normalize_name(player_team),
                "team_a": DFSBookBase.clean_and_normalize_name(team_a),
                "team_b": DFSBookBase.clean_and_normalize_name(team_b),
                "team_key": game_key,
                "team_a_abbreviation": abbreviation_split.get("team_a"),
                "team_b_abbreviation": abbreviation_split.get("team_b"),
            }


    @staticmethod
    def _extract_solo_games(game_section, player_name):
        """Extract Solo Game Details"""
        valid_split = BookBase._split_teams(game_section.get("title").replace(".", ""))
        if valid_split:
            team_a = valid_split["team_a"]
            team_b = valid_split["team_b"]
            game_key = BookBase._generate_key([team_a, team_b, game_section.get("scheduled_at")])
        else:
            team_a = None
            team_b = None

            full_title = game_section.get("full_title")
            if full_title:
                full_title = full_title.replace("-", "").replace("_", "").replace(".", "")
                full_title = re.sub(r"\s+", " ", full_title).strip()
                game_key = BookBase._generate_key([player_name, full_title, game_section.get("scheduled_at")])

        return {
            "match_title": game_section.get("title").strip(),
            "player_team": DFSBookBase.clean_and_normalize_name(player_name),
            "team_a": DFSBookBase.clean_and_normalize_name(team_a),
            "team_b": DFSBookBase.clean_and_normalize_name(team_b),
            "team_key": game_key,
        }

    @staticmethod
    def _get_game_details(game_section, game_type, player_name, team_id):
        """Get the game details for Solo Games and Team Games"""
        full_details = {
            "start_date": game_section.get("scheduled_at"),
        }

        if game_type == "Game":
            team_data = Underdog._extract_team_games(game_section, team_id, player_name)
            team_data["solo_game"] = False
            full_details.update(**team_data)
        else:
            solo_data = Underdog._extract_solo_games(game_section, player_name)
            solo_data["solo_game"] = True
            full_details.update(**solo_data)

        return full_details

    @staticmethod
    def __extract_stats(line_section):
        """Extract Stats Details"""

        def check_half_market(stat):
            match = re.search(r"\b(\d)([HQ])\b", stat)
            if match:
                number, period = match.groups()
                number_map = {
                    '1': '1st',
                    '2': '2nd',
                    '3': '3rd',
                    '4': '4th'
                }
                if period == 'H':
                    return f"{number_map.get(number, number + 'th')} half"
                elif period == 'Q':
                    return f"{number_map.get(number, number + 'th')} quarter"

            return "full"

        def set_payout_label(payout_multiplier):
            """Set the payout label"""
            if payout_multiplier > 1:
                return "payout boost"
            elif payout_multiplier < 1:
                return "reduced payout"
            return "standard"

        choice_mapping = {
            "higher": "over",
            "lower": "under",
            "better": "over",
            "worse": "under",
        }

        return [
            Stats(
                stat_type=line_section.get("over_under", {}).get("appearance_stat", {}).get("display_stat").strip().title(),
                line=float(line_section.get("stat_value")),
                bet_direction=choice_mapping.get(option.get("choice")),
                regular_line=True if option.get("payout_multiplier") == 0 else False,
                optional_stats={
                    "market_type": check_half_market(line_section.get("over_under", {}).get("appearance_stat", {}).get("display_stat")),
                    "odds_type": set_payout_label(float(option.get("payout_multiplier", 0))),
                    "multiplier": float(option.get("payout_multiplier")),
                    "odds": {
                        "american_odds": float(option.get("american_price")),
                        "decimal_odds": float(option.get("decimal_price"))
                    }

                }
            )

            for option in line_section.get("options", [])
        ]


    def _extract_api_data(self, map_data, appearance_data):
        if not (player_id := appearance_data.get("player_id")) or not (
        game_id := appearance_data.get("match_id")) or not (line_id := appearance_data.get("id")):
            return

        player_details = Underdog._extract_player_info(map_data.get("players").get(player_id))

        game_type = appearance_data.get("match_type")  # Game or SoloGame

        game_details = Underdog._get_game_details(
            game_section=map_data.get("team_games").get(game_id) if game_type == "Game" else map_data.get(
                "solo_games").get(game_id),
            game_type=game_type,
            # player_name=player_details.get("full_name"),
            player_name=player_details.get("player_name"),
            team_id=player_details.get("team_id") if game_type == "Game" else None,
        )
        league = self.league_mapping.get(player_details.get("league").lower(), player_details.get("league"))

        stat_details = Underdog.__extract_stats(map_data.get("lines").get(line_id))

        return PlayerData(
            player_name= player_details.get("player_name"),
            league=league,
            start_date= game_details.get("start_date"),
            solo_game=game_details.get("solo_game"),
            future=True if "szn" in league.lower() else False,
            team_data=TeamData(
                team_a=game_details.get("team_a"),
                team_b=game_details.get("team_b"),
                team_key=game_details.get("team_key"),
                player_team=game_details.get("player_team"),
                team_a_abbreviation=game_details.get("team_a_abbreviation"),
                team_b_abbreviation=game_details.get("team_b_abbreviation"),
            ),
            stats=stat_details
        )

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method
            )

            if not api_data:
                self._api_call_log("underdog")

            map_data = Underdog._mapper(api_data)
            underdog_data = [
                data for player in api_data.get("appearances", [])
                if (data := self._extract_api_data(map_data, player))
            ]

            data = await self._database_mapper(underdog_data)
            serialized_data = self._serialize_data(data)


            ### TRY SWITHC MODEL WITHOUT WEB SEARCH TO SEE IF IT WORKS, OR USE WEB SEARCH ONLY FOR TENNIS ETC.





if __name__ == "__main__":
    underdog = Underdog()
    asyncio.run(underdog.run_book())

