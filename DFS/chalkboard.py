import json

import aiohttp

from Settings.book_base import SportbookRequestType
from Settings.dfs_book_base import DFSBookBase


class Chalkboard(DFSBookBase):
    def __init__(self):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="chalkboard")
        self.valid_markets = [
            "Map 1-2 Headshots",
            "Map 1-2 Kills",
        ]


    @staticmethod
    def _generate_payload():
        return {
            "structuredQuery": {
                "from": [{"collectionId": "dfs_legs"}],
                "where": {
                    "compositeFilter": {
                        "op": "AND",
                        "filters": [
                            {
                                "fieldFilter": {
                                    "field": {"fieldPath": "gameType"},
                                    "op": "EQUAL",
                                    "value": {"stringValue": "cs2"},
                                }
                            }
                        ],
                    }
                },
            }
        }

    def _filter_markets(self, raw_data):
        return [
            {
                "book_name": "chalkboard",
                "league": "CS2",
                "start_time": raw.get("document", {}).get("fields", {}).get("scheduled", {}).get("stringValue"),
                "player_name": raw.get("document", {}).get("fields", {}).get("player", {}).get("mapValue", {}).get("fields", {}).get("full_name", {}).get("stringValue"),
                "line": raw.get("document", {}).get("fields", {}).get("line", {}).get("doubleValue"),
                "over_prob": raw.get("document", {}).get("fields", {}).get("markets", {}).get("mapValue", {}).get("fields", {}).get("over", {}).get("mapValue", {}).get("fields", {}).get("probabilities", {}).get("doubleValue"),
                "over_odds": raw.get("document", {}).get("fields", {}).get("markets", {}).get("mapValue", {}).get("fields", {}).get("over", {}).get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue"),
                "under_prob": raw.get("document", {}).get("fields", {}).get("markets", {}).get("mapValue", {}).get("fields", {}).get("under", {}).get("mapValue", {}).get("fields", {}).get("probabilities", {}).get("doubleValue"),
                "under_odds": raw.get("document", {}).get("fields", {}).get("markets", {}).get("mapValue", {}).get("fields", {}).get("under", {}).get("mapValue", {}).get("fields", {}).get("odds", {}).get("stringValue"),

                "stat_type": raw.get("document", {}).get("fields", {}).get("statisticName", {}).get("stringValue"),
                "team_a": raw.get("document", {}).get("fields", {}).get("away", {}).get("mapValue", {}).get("fields", {}).get("name", {}).get("stringValue"),
                "team_b": raw.get("document", {}).get("fields", {}).get("home", {}).get("mapValue", {}).get("fields", {}).get("name", {}).get("stringValue"),
            }
            for raw in raw_data
            if raw.get("document", {}).get("fields", {}).get("statisticName", {}).get("stringValue") in self.valid_markets
        ]

    def chalkboard_ui_multiplier(self,odds: float, scale: float = 0.888, decimals: int = 2) -> float:
        return round(odds * scale, decimals)

    async def run_book(self):
        async with aiohttp.ClientSession() as session:
            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("main_url"),
                headers=self.book_data.headers,
                method=self.book_data.method,
                payload=Chalkboard._generate_payload(),
            )
            data_filter = self._filter_markets(api_data)
            # print(data)

            with open("raw_chalkboard_filter.json", "w") as file:
                json.dump(data_filter, file, indent=2)

            with open("raw_chalkboard.json.json", "w") as file:
                json.dump(api_data, file, indent=2)


if __name__ == "__main__":
    import asyncio

    chalk = Chalkboard()
    asyncio.run(chalk.run_book())