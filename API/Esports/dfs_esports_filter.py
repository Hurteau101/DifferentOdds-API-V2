import json

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
            for line_data in extra_data.get("data", []):
                if line_data.get("league") in self.ESPORT_LEAGUES:
                    if book not in esports_only:
                        esports_only[book] = {
                            "last_refresh": extra_data.get("last_refresh"),
                            "data": []
                        }

                    esports_only[book]["data"].append(line_data)

        return esports_only










