class BaseFormatter:
    def format(self, data):
        raise NotImplementedError

class TempFormatter:
    def format(self, data):
        games = {}

        for book, extra_data in data.items():
            if book not in games:
                games[book] = {}

            if not extra_data:
                games[book] = None
                continue

            for entry in extra_data.get("data", []):
                game_key = entry.get("team_data", {}).get("team_key")

                if game_key not in games[book]:
                    if entry.get("solo_game") or entry.get("future"):
                        team_a = entry.get("team_data", {}).get("team_a")
                        team_b = entry.get("team_data", {}).get("team_b")

                        teams = (
                            [{"name": team} for team in (team_a, team_b) if team_a and team_b]
                            if team_a and team_b
                            else [{"name": entry.get("player_name")}]
                        )
                    else:
                        teams = [
                            {"name": entry.get("team_data", {}).get("team_a")},
                            {"name": entry.get("team_data", {}).get("team_b")},
                        ]

                    games[book][game_key] = {
                        "league": entry.get("league"),
                        "start_date": entry.get("start_date"),
                        "teams": teams,
                        "solo_game": entry.get("solo_game", False),
                        "combo": entry.get("combo", False),
                        "future": entry.get("future", False),
                        "odds": [],
                        "static_info": [],
                        "discounted_odds": [],
                    }

                for stat in entry.get("stats", []):
                    optional_stats = stat.get("optional_stats", {})

                    optional_stats_formatted = {
                        "odds_type": optional_stats.get("odds_type"),
                        "market_type": optional_stats.get("market_type"),
                        "over_price_american": f"+{int(optional_stats.get('odds', {}).get('american_odds', 0))}"
                        if optional_stats.get("odds", {}).get("american_odds") is not None
                        else None,
                        "over_price_decimal": optional_stats.get("odds", {}).get("decimal_odds"),
                        "over_multiplier": optional_stats.get("multiplier"),
                        "stat_id": stat.get("id") or optional_stats.get("stat_id"),
                    }

                    stat_data = {
                        "player_name": entry.get("player_name"),
                        "regular": stat.get("regular_line"),
                        "stat_type": f'Player {stat.get("stat_type")}',
                        "line": stat.get("line"),
                        "bet_type": stat.get("bet_direction"),
                        "optional_stats": optional_stats_formatted,
                    }

                    games[book][game_key]["odds"].append(stat_data)

                    if stat.get("discounts") and stat.get("discounts", {}).get("discount_name"):
                        games[book][game_key]["discounted_odds"].append(stat.get("discounts", {}))

        return games


class GameFormatter(BaseFormatter):
    def format(self, data):
        games = {}

        for book, extra_data in data.items():
            if book not in games:
                # games[book] = []
                games[book] = {}

            if not extra_data:
                games[book] = None
                continue

            for entry in extra_data.get("data", []):
                game_key = entry.get("team_data", {}).get("team_key")

                if game_key not in games[book]:
                    if entry.get("solo_game") or entry.get("future"):
                        team_a = entry.get("team_data", {}).get("team_a")
                        team_b = entry.get("team_data", {}).get("team_b")

                        teams = [
                            {
                                "team_a": team_a,
                                "team_b": team_b,
                            }
                        ] if team_a and team_b else [{"player": entry.get("player_name")}]
                    else:
                        teams = [
                            {
                                "team_a": entry.get("team_data", {}).get("team_a"),
                                "team_a_abbreviation": entry.get("team_data", {}).get("team_a_abbreviation", None),
                                "team_b": entry.get("team_data", {}).get("team_b"),
                                "team_b_abbreviation": entry.get("team_data", {}).get("team_b_abbreviation", None),
                            }
                        ]

                    games[book][game_key] = {
                        "league": entry.get("league"),
                        "start_date": entry.get("start_date"),
                        "teams": teams,
                        "solo_game": entry.get("solo_game", False),
                        "combo": entry.get("combo", False),
                        "future": entry.get("future", False),
                        "odds": [],
                        "discounted_odds": [],
                    }

                    # game_dict = {
                    #     game_key: {
                    #     "league": entry.get("league"),
                    #     "start_date": entry.get("start_date"),
                    #     "teams": teams,
                    #     "solo_game": entry.get("solo_game", False),
                    #     "combo": entry.get("combo", False),
                    #     "odds": [],
                    #     "discounted_odds": [],
                    #     }
                    # }

                for stat in entry.get("stats", []):
                    stat_data = {
                        "player_name": entry.get("player_name"),
                        "stat_type": stat.get("stat_type"),
                        "line": stat.get("line"),
                        "bet_type": stat.get("bet_direction"),
                        "regular_line": stat.get("regular_line"),
                        **stat.get("optional_stats", {}),
                    }

                    games[book][game_key]["odds"].append(stat_data)
                    # game_dict[game_key]["odds"].append(stat_data)
                    if stat.get("discounts") and stat.get("discounts", {}).get("discount_name"):
                        games[book][game_key]["discounted_odds"].append(stat.get("discounts", {}))
                        # game_dict[game_key]["discounted_odds"].extend(stat.get("discounts", []))

        return games


def get_formatter(format_name, redis_data):
    mapping = {
        "game": GameFormatter,
        "temp": TempFormatter,
    }

    formatter = mapping[format_name]()
    return formatter.format(redis_data)



# if __name__ == "__main__":
#     import json
#     with open("response.json", "r", encoding="utf-8") as f:
#         sample_data = json.load(f)
#
#
#     formatted_league = get_formatter("league", sample_data)
    # formatted_game = get_formatter("game", sample_data)

    # print(formatted_league)
    # print(formatted_game)