from Books.Prediction_Liquidity.novig import Novig
from Books.Prediction_Liquidity.prophetx import Prophetx
from Redis.redis_manager import RedisAsyncManager
import json
import asyncio

class LiquidityCompare:
    def _create_selection_mapping(self, books: dict):
        combined = {}

        for index, (book_name, book_data) in enumerate(books.items()):
            if index == 0 and book_name != "novig":
                raise ValueError("Novig should be first in the books dictionary, as their times are usually off.")

            for game in book_data:
                book_selection_key = game.get("selection_key", {})
                selection_key = (
                    book_selection_key.get("event_name"),
                    book_selection_key.get("market"),
                    book_selection_key.get("line"),
                    book_selection_key.get("bet_type"),
                    book_selection_key.get("bet_team"),
                    book_selection_key.get("bet_player"),
                )

                start_date = game.get("start_date", "").replace("T", "_")
                event_name = game.get("event_name")

                bettorodds_key = "_".join(
                    str(value) for value in [
                        start_date,
                        event_name,
                        book_selection_key.get("market"),
                        book_selection_key.get("bet_type"),
                        book_selection_key.get("line"),
                        book_selection_key.get("bet_team"),
                    ] if value is not None
                ).replace(" ", "_").replace("-", "_").lower()

                event_data = combined.setdefault(event_name, {
                    "league": game.get("league"),
                    "start_date": game.get("start_date"),
                    "event_name": event_name,
                    "odds_map": {}
                })

                selection = event_data["odds_map"].setdefault(selection_key, {
                    "market": book_selection_key.get("market"),
                    "line": book_selection_key.get("line"),
                    "bettorodds_key": bettorodds_key,
                    "bet_type": book_selection_key.get("bet_type"),
                    "bet_team": book_selection_key.get("bet_team"),
                    "bet_player": book_selection_key.get("bet_player"),

                    "books": {},
                    "games": {}
                })

                selection["books"][book_name] = game.get("liquidity_data")
                selection["games"][book_name] = game

        return combined

    def add_book_feed(self, bettorodds_data: dict, merged_data: list):
        excluded_values = {
            "bettorodds_key",
            "market",
            "line",
            "bet_type",
            "bet_team",
            "bet_player"
        }

        unmatched_data = []
        matched_data = []

        for event in merged_data:
            odds_list = []

            for odds in event["odds"]:
                odds_key = odds.get("bettorodds_key")
                if not odds_key:
                    continue

                matched_bettorodds = bettorodds_data.get(odds_key, {})
                book_feed = matched_bettorodds.get("book_feed", {})

                if not book_feed:
                    continue

                odds["nvig_map"] = matched_bettorodds.get("nvig_map", {})
                existing_books = set(odds) - excluded_values

                new_books = {
                    book: values
                    for book, values in book_feed.items()
                    if book not in existing_books
                }

                if new_books:
                    odds["book_feed"] = new_books
                    odds_list.append(odds)

            if odds_list:
                matched_data.append({
                    "league": event["league"],
                    "start_date": event["start_date"],
                    "event_name": event["event_name"],
                    "odds": odds_list
                })

                continue

            unmatched_data.append(event)

        return matched_data, unmatched_data

    def compare_books(self, books: dict, min_books: int = 2) -> tuple:
        selection_mapping = self._create_selection_mapping(books)

        matched = []
        unmatched = {book: [] for book in books}

        for mapping in selection_mapping.values():
            odds_list = []

            for selection in mapping["odds_map"].values():
                book_count = len(selection["books"])
                if book_count >= min_books:
                    odds_list.append({
                        "bettorodds_key": selection["bettorodds_key"],
                        "market": selection["market"],
                        "line": selection["line"],
                        "bet_type": selection["bet_type"],
                        "bet_team": selection["bet_team"],
                        "bet_player": selection["bet_player"],
                        **selection["books"]
                    })

                    continue

                for book_name, game in selection["games"].items():
                    unmatched[book_name].append(game)


            if odds_list:
                matched.append({
                    "league": mapping["league"],
                    "start_date": mapping["start_date"],
                    "event_name": mapping["event_name"],
                    "odds": odds_list
                })

        return matched, unmatched


    def reformat_bettorodds_data(self, raw_bettorodds_data: dict):
        bettorodds_data = {}

        for record in raw_bettorodds_data.values():
            record_id = record.get("ID", "")
            id_split = record_id.split("__")

            if len(id_split) > 1 and "_vs_" in id_split[1]:
                teams = id_split[1].split("_vs_")
                id_split[1] = "_vs_".join(sorted(teams))

            record_id = "_".join(id_split).replace(" ", "_").lower()

            bettorodds_data[record_id] = record

        return bettorodds_data


    async def run(self, test_mode: bool = False):
        liquidity_redis_instance = RedisAsyncManager(database=7)
        bettorodds_redis_instance = RedisAsyncManager(database=8)

        # Ensure Novig is already first, as there times are usually off.
        books = {
            "novig": await liquidity_redis_instance.get_data("novig"),
            "prophetx": await liquidity_redis_instance.get_data("prophetx"),
        }

        merged, unmatched = self.compare_books(books)

        bettorodds_sportsbook_data = await bettorodds_redis_instance.get_data("bettoroddds_odds")

        if not bettorodds_sportsbook_data:
            return

        formated_bettorodds = self.reformat_bettorodds_data(bettorodds_sportsbook_data)

        finalized_map, finalized_unmapped = self.add_book_feed(formated_bettorodds, merged)

        print(finalized_map)

        if finalized_map:
            await liquidity_redis_instance.store_data(
                key_name=f"liquidity_comparison",
                data_to_store=finalized_map,
                key_expiration=120000
            )

        if test_mode:
            with open("finalized_map.json", "w") as file:
                json.dump(finalized_map, file, indent=2)

            with open("finalized_unmapped.json", "w") as file:
                json.dump(finalized_unmapped, file, indent=2)

            with open("formatted_bettorodds.json", "w") as file:
                json.dump(formated_bettorodds, file, indent=2)

            with open("raw_bettorodds.json", "w") as file:
                json.dump(bettorodds_sportsbook_data, file, indent=2)

            with open("merged.json", "w") as f:
                json.dump(merged, f, indent=2)

            # Save unmatched per book
            for book_name, data in unmatched.items():
                filename = f"{book_name.lower()}_unmatched.json"

                with open(filename, "w") as f:
                    json.dump(data, f, indent=2)






if __name__ == "__main__":
    compare_instance = LiquidityCompare()
    asyncio.run(compare_instance.run(test_mode=True))