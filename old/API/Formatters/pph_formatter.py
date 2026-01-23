from celery.utils.log import get_task_logger


class BaseFormatter:
    """Base formatter that returns data as-is."""
    def format(self, data):
        return data

logger = get_task_logger(__name__)
class GameFormatter(BaseFormatter):
    def format(self, data):
        games = {}

        for entry in data:
            team_data = entry.get("team_data")
            game_key = team_data.get("team_key")

            games[game_key] = {
                "league": entry.get("league"),
                "start_date": entry.get("start_date"),
                "teams": [
                    {
                        "team_a": team_data.get("team_a"),
                        "team_a_abbreviation": team_data.get("team_a_abbreviation"),
                        "team_b": team_data.get("team_b"),
                        "team_b_abbreviation": team_data.get("team_b_abbreviation"),
                    }
                ],
                "solo_game": entry.get("solo_game"),
                "future": entry.get("future"),
            }

            for odds in entry.get("odds", []):
                odds_data = {
                    "market": odds.get("market"),
                    "american_odds": odds.get("american_odds"),
                    "bet_team": odds.get("bet_team"),
                    "bet_type": odds.get("bet_type"),
                    "line": odds.get("line"),
                    "bet_player": odds.get("bet_player"),
                }

                games[game_key].setdefault("odds", []).append(odds_data)

        return games

def get_pph_formatter(format_name, redis_data):
    mapping = {
        "base": BaseFormatter,
        "game": GameFormatter,
    }

    formatter = mapping[format_name]()
    return formatter.format(redis_data)