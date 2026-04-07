from datetime import datetime

ESPORT_LEAGUES = [
    "LOL", "CS2", "DOTA2", "VAL", "COD", "APEX", "R6"
]


def extract_esport_lines(lines):
    """Only get Esports related data from the full DFS dataset."""
    esports_only = {}

    for book, extra_data in lines.items():
        if extra_data:
            book_data = {}

            for line_data in extra_data.values():
                if line_data.get("league") in ESPORT_LEAGUES:
                    for odds in line_data.get("odds", []):
                        player_name = odds.get("player_name")
                        book_data.setdefault(player_name, {
                            "player_name": player_name,
                            "player_team": odds.get("player_team"),
                            "league": line_data.get("league"),
                            "start_date": line_data.get("start_date"),
                            "team_data": line_data.get("teams")[0] if line_data.get("teams") else {},
                            "stats": []
                        })

                        book_data[player_name]["stats"].append({
                            "stat_type": odds.get("stat_type"),
                            "line": odds.get("line"),
                            "bet_direction": odds.get("bet_type"),
                            "regular_line": odds.get("regular_line"),
                            "player_id": odds.get("player_id"),
                            "optional_stats": {
                                "market_type": odds.get("market_type"),
                                "odds_type": odds.get("odds_type"),
                                "multiplier": odds.get("multiplier", 1.0),
                                "odds": odds.get("odds", {}) if odds and odds.get("odds_format") else None,
                                "betlink": odds.get("betlink", {}),
                            }
                        })

            esports_only.setdefault(book, {
                "last_refresh": datetime.now().isoformat(),
                "data": list(book_data.values())
            })

    return esports_only


def find_highest_discrep(differences: dict):
    for key, esport_values in differences.items():
        lines = [book["line"] for book in esport_values.get("books", [])]
        highest_line = max(lines)
        lowest_line = min(lines)
        discrep = abs(highest_line - lowest_line)
        differences[key]["highest_discrepancy"] = discrep

    return differences

def create_differences(esports_data):
    """Create a structure to identify differences in esports DFS lines across books."""

    differences = {}

    for book_name, book_data in esports_data.items():
        for entry in book_data.get("data", []):
            player_name = entry.get("player_name").lower() if entry.get("player_name") else None
            start_date = entry.get("start_date", None)
            league = entry.get("league").upper() if entry.get("league") else None

            if not all([player_name, start_date, league]):
                continue

            if entry.get("is_combo"):
                continue

            team_data = entry.get("team_data", {})
            teams = sorted([team_data.get("team_a").strip(), team_data.get("team_b").strip()])

            if league in ["COD"]:
                player_key = f"{player_name}-{league}-{''.join(teams)}"
            else:
                player_key = f"{player_name}-{league}-{start_date}"

            team_a = teams[0]
            team_b = teams[1]

            player_team = entry.get("player_team") or team_data.get("player_team")

            opponent = team_b if player_team.lower() != team_b.lower() else team_a

            for stat in entry.get("stats", []):
                stat_type = stat.get("stat_type").lower()
                stat_key = f"{player_key}-{stat_type}-{opponent.lower()}"
                team_list = sorted([team_a.lower(), team_b.lower()])
                game = " vs ".join(team_list)

                if stat_key not in differences:
                    differences[stat_key] = {
                        "player_name": player_name,
                        "start_date": start_date,
                        "league": league,
                        "player_team": player_team,
                        "opponent": opponent,
                        "game": game,
                        "stat_type": stat_type,
                        "books": []
                    }

                book_entry = next(
                    (book for book in differences[stat_key]["books"] if
                     book["book_name"] == book_name),
                    None
                )

                if not book_entry:
                    book_entry = {
                        "book_name": book_name,
                        "betlink": stat.get("optional_stats").get("betlink", {}) if book_name == "prizepicks" else {},
                        "line": stat.get("line"),
                        "directions": []
                    }
                    differences[stat_key]["books"].append(book_entry)

                if book_name == "prizepicks":
                    multiplier = 1 if stat.get("regular_line") else 1.01
                else:
                    multiplier = stat.get("optional_stats", {}).get("multiplier") if stat.get("optional_stats", {}).get("multiplier") else 1

                direction = {
                    "bet_direction": stat.get("bet_direction"),
                    "multiplier": multiplier,
                }
                if direction not in book_entry["directions"]:
                    book_entry["directions"].append(direction)

    differences = find_highest_discrep(differences)

    filtered = {k: v for k, v in sorted(differences.items()) if len(v["books"]) > 1}

    return dict(
        sorted(
            filtered.items(),
            key=lambda item: item[1].get("highest_discrepancy", 0),
            reverse=False
        )
    )




