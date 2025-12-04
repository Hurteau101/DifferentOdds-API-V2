class BaseFormatter:
    """Base formatter that returns data as-is."""
    def format(self, data):
        return data


class GameFormatter(BaseFormatter):
    def format(self, data):
        games = {}

        for entry in data:
            team_data = entry.team_data
            game_key = team_data.team_key

            games[game_key] = {
                "league": entry.league,
                "start_date": entry.start_date,
                "teams": [
                    {
                        "team_a": entry.team_data.team_a,
                        "team_a_abbreviation": entry.team_data.team_a_abbreviation,
                        "team_b": entry.team_data.team_b,
                        "team_b_abbreviation": entry.team_data.team_b_abbreviation,
                    }
                ],
                "solo_game": entry.solo_game,
                "future": entry.future,
            }

            for odds in entry.odds:
                odds_data = {
                    "market": odds.market,
                    "american_odds": odds.american_odds,
                    "bet_team": odds.bet_team,
                    "bet_type": odds.bet_type,
                    "line": odds.line,
                    "bet_player": odds.bet_player,
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