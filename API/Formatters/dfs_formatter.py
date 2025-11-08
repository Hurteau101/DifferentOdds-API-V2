class BaseFormatter:
    """Base formatter that returns data as-is."""
    def format(self, data):
        return data

class GameFormatter(BaseFormatter):
    """Formats DFS data into a game-centric structure."""
    def format(self, data):
        games = {}

        for entry in data:
            team_data = entry.get("team_data", {}) or {}
            game_key = team_data.get("team_key")

            if not game_key:
                continue

            if game_key not in games:
                if entry.get("solo_game") or entry.get("future"):
                    team_a = team_data.get("team_a")
                    team_b = team_data.get("team_b")

                    teams = (
                        [{"name": team} for team in (team_a, team_b) if team]
                        if team_a and team_b
                        else [{"player": entry.get("player_name")}]
                    )
                else:
                    teams = [
                        {
                            "team_a": team_data.get("team_a"),
                            "team_a_abbreviation": team_data.get("team_a_abbreviation"),
                            "team_b": team_data.get("team_b"),
                            "team_b_abbreviation": team_data.get("team_b_abbreviation"),
                        }
                    ]

                games[game_key] = {
                    "league": entry.get("league"),
                    "start_date": entry.get("start_date"),
                    "teams": teams,
                    "solo_game": entry.get("solo_game", False),
                    "combo": entry.get("combo", False),
                    "future": entry.get("future", False),
                    "odds": [],
                    "discounted_odds": [],
                }

            # Append all stats for the player to this game
            for stat in entry.get("stats", []):
                stat_data = {
                    "player_name": entry.get("player_name"),
                    "stat_type": f'Player {stat.get("stat_type")}',
                    "line": stat.get("line"),
                    "bet_type": stat.get("bet_direction"),
                    "regular_line": stat.get("regular_line"),
                    **stat.get("optional_stats", {}),
                }

                games[game_key]["odds"].append(stat_data)

                if stat.get("discounts") and stat["discounts"].get("discount_name"):
                    games[game_key]["discounted_odds"].append(stat["discounts"])

        return games


def get_formatter(format_name, redis_data):
    mapping = {
        "base": BaseFormatter,
        "game": GameFormatter,
    }

    formatter = mapping[format_name]()
    return formatter.format(redis_data)