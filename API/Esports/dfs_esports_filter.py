class Esports:
    ESPORT_LEAGUES = [
        "LOL", "CS2", "DOTA2", "VAL", "COD"
    ]

    def __init__(self, raw_dfs_data):
        self.data = raw_dfs_data

    def get_esport_lines(self):
        """Only get Esports related data from the full DFS dataset."""
        esports_only = {}

        for book, extra_data in self.data.items():
            if extra_data:
                for line_data in extra_data.get("data", []):
                    if line_data.get("league") in self.ESPORT_LEAGUES:
                        if book not in esports_only:
                            esports_only[book] = {
                                "last_refresh": extra_data.get("last_refresh"),
                                "data": []
                            }

                        esports_only[book]["data"].append(line_data)

        return esports_only

    def create_differences(self, esports_data):
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

                player_key = f"{player_name}-{start_date}-{league}"
                team_data = entry.get("team_data", {})
                teams = sorted([team_data.get("team_a").strip(), team_data.get("team_b").strip()])

                team_a = teams[0]
                team_b = teams[1]

                player_team = team_data.get("player_team")

                opponent = team_b if player_team.lower() != team_b.lower() else team_a

                for stat in entry.get("stats", []):
                    stat_type = stat.get("stat_type").lower()
                    stat_key = f"{player_key}-{stat_type}-{opponent.lower()}"

                    if stat_key not in differences:
                        stat_details = {
                            "player_name": player_name,
                            "start_date": start_date,
                            "league": league,
                            "player_team": player_team,
                            "opponent": opponent,
                            "stat_type": stat_type,
                            "books": []
                        }

                        differences[stat_key] = stat_details

                    book_entry = next(
                        (book for book in differences[stat_key]["books"] if
                         book["book_name"] == book_name and book["line"] == stat.get("line")),
                        None
                    )

                    if not book_entry:
                        book_entry = {
                            "book_name": book_name,
                            "line": stat.get("line"),
                            "directions": []
                        }
                        differences[stat_key]["books"].append(book_entry)

                    if book_name == "prizepicks":
                        multiplier = 1 if stat.get("regular_line") else 1.01 # Using 1.01 to indicate a non-regular line
                    else:
                        multiplier = stat.get("optional_stats", {}).get("multiplier")

                    book_entry["directions"].append({
                        "bet_direction": stat.get("bet_direction"),
                        "multiplier": multiplier,
                    })


        # Only keep entries that have more than one book offering
        return  {k: v for k, v in differences.items() if len(v["books"]) > 1}

# def count_books_per_league(data):
#     league_counts = {}
#     seen_players = {}  # track players per league
#
#     for entry in data.values():
#         league = entry["league"]
#         player = entry["player_name"]
#         stat_type = entry["stat_type"]
#         player_key = f"{player}-{stat_type}"
#
#         book_names = {book["book_name"].lower() for book in entry["books"]}
#         if "underdog" in book_names and "prizepicks" in book_names:
#             if league not in seen_players:
#                 seen_players[league] = set()
#             if player_key not in seen_players[league]:
#                 seen_players[league].add(player_key)
#                 league_counts[league] = league_counts.get(league, 0) + 1
#
#     # print("List of seen players", seen_players)
#     return league_counts
#











