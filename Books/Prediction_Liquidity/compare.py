# from Redis.redis_manager import RedisAsyncManager
# import json
# import asyncio
#
# def index_book(book_data):
#     index = {}
#
#     for game in book_data:
#         sk = game.get("selection_key", {})
#
#         selection_key = (
#             sk.get("event_name"),
#             sk.get("market"),
#             sk.get("line"),
#             sk.get("bet_type"),
#             sk.get("bet_team"),
#             sk.get("bet_player"),
#         )
#
#         index[selection_key] = game
#
#     return index
#
# def intersect_books(index_a, index_b, name_a, name_b):
#     found_data = {}
#
#
#     common_games = index_a.keys() & index_b.keys()
#     print(f"Total Matches: {len(common_games)}")
#
#     for common in common_games:
#         found_a = index_a[common]
#         found_b = index_b[common]
#
#         game_details = {
#             "league": found_a["league"],
#             "start_date": found_a["start_date"],
#             "event_name": found_a["event_name"],
#             # **found_a["selection_key"],
#             # "odds": {
#             #     name_a: found_a["liquidity_data"],
#             #     name_b: found_b["liquidity_data"]
#             # }
#         }
#
#         odds = {
#             "market": found_a["selection_key"]["market"],
#             # "event_name": found_a["selection_key"]["event_name"],
#            "line": found_a["selection_key"]["line"],
#            "bet_type": found_a["selection_key"]["bet_type"],
#            "bet_team": found_a["selection_key"]["bet_team"],
#            "bet_player": found_a["selection_key"]["bet_player"],
#             name_a: found_a["liquidity_data"],
#             name_b: found_b["liquidity_data"]
#         }
#
#
#         found_data.setdefault(found_a["event_name"], {
#             **game_details,
#             "odds": []
#         })["odds"].append(odds)
#
#     return list(found_data.values())
#
# def find_unmatched(index_a, index_b):
#     unmatched_keys = index_a.keys() - index_b.keys()
#     return [index_a[key] for key in unmatched_keys]
#
# async def compare():
#     redis_instance = RedisAsyncManager(database=7)
#     novig = await redis_instance.get_data("novig")
#     prophetx = await redis_instance.get_data("prophetx")
#
#     # with open("prophetx.json", "w") as f:
#     #     json.dump(prophetx, f, indent=2)
#
#     with open("novig.json", "w") as f:
#         json.dump(novig, f, indent=2)
#
#     novig_index = index_book(novig)
#     prophetx_index = index_book(prophetx)
#
#     data = intersect_books(novig_index, prophetx_index, "Novig", "Prophetx")
#
#     with open("merged.json", "w") as f:
#         json.dump(data, f, indent=2)
#
#     novig_unmatched = find_unmatched(novig_index, prophetx_index)
#     prophetx_unmatched = find_unmatched(prophetx_index, novig_index)
#
#     with open("novig_unmatched.json", "w") as f:
#         json.dump(novig_unmatched, f, indent=2)
#
#     with open("prophetx_unmatched.json", "w") as f:
#         json.dump(prophetx_unmatched, f, indent=2)
#
# asyncio.run(compare())
from os.path import split

from Redis.redis_manager import RedisAsyncManager
import json
import asyncio


def combine_books(books, min_books=2):
    combined = {}

    for book_name, book_data in books.items():
        for game in book_data:

            sk = game.get("selection_key", {})

            selection_key = (
                sk.get("event_name"),
                sk.get("market"),
                sk.get("line"),
                sk.get("bet_type"),
                sk.get("bet_team"),
                sk.get("bet_player"),
            )

            game_time = game.get("start_date", "").replace("T", "_")
            event_name = game.get("event_name")

            bettorodds_key = "_".join(
                str(v) for v in [
                    game_time,
                    event_name,
                    sk.get("market"),
                    sk.get("bet_type"),
                    sk.get("line")
                ] if v is not None
            ).replace(" ", "_").replace("-", "_").lower()

            event = combined.setdefault(event_name, {
                "league": game.get("league"),
                "start_date": game.get("start_date"),
                "event_name": event_name,
                "odds_map": {}
            })

            selection = event["odds_map"].setdefault(selection_key, {
                "market": sk.get("market"),
                "line": sk.get("line"),
                "bettorodds_key": bettorodds_key,
                "bet_type": sk.get("bet_type"),
                "bet_team": sk.get("bet_team"),
                "bet_player": sk.get("bet_player"),

                "books": {},
                "games": {}
            })

            selection["books"][book_name] = game.get("liquidity_data")
            selection["games"][book_name] = game

    results = []
    unmatched = {book: [] for book in books}

    for event in combined.values():

        odds_list = []

        for sel in event["odds_map"].values():

            book_count = len(sel["books"])

            if book_count >= min_books:

                odds = {
                    "bettorodds_key": sel["bettorodds_key"],
                    "market": sel["market"],
                    "line": sel["line"],
                    "bet_type": sel["bet_type"],
                    "bet_team": sel["bet_team"],
                    "bet_player": sel["bet_player"],
                    **sel["books"]
                }

                odds_list.append(odds)

            else:
                # Only one book had this selection
                for book_name, game in sel["games"].items():
                    unmatched[book_name].append(game)

        if odds_list:
            results.append({
                "league": event["league"],
                "start_date": event["start_date"],
                "event_name": event["event_name"],
                "odds": odds_list
            })

    return results, unmatched

def _reformat_bettorodds(bettorodds: dict):
    odds = {}

    for record in bettorodds.values():
        record_id = record.get("ID", "")
        id_split = record_id.split("__")

        if len(id_split) > 1 and "_vs_" in id_split[1]:
            teams = id_split[1].split("_vs_")
            id_split[1] = "_vs_".join(sorted(teams))

        record_id = "_".join(id_split).replace(" ", "_").lower()

        odds[record_id] = record

    return odds

def add_book_feed(bettorodds_data: dict, merged_data: list):

    matched_data = []
    unmatched_data = []

    excluded_values = {
        "bettorodds_key",
        "market",
        "line",
        "bet_type",
        "bet_team",
        "bet_player"
    }

    for event in merged_data:

        valid_odds = []

        for odds in event["odds"]:

            odds_key = odds.get("bettorodds_key")
            if not odds_key:
                continue

            book_feed = bettorodds_data.get(odds_key, {}).get("book_feed")
            if not book_feed:
                continue

            existing_books = set(odds) - excluded_values
            key_checker = odds.get("bet_type") or odds.get("bet_team")


            # new_books = {
            #     book: values
            #     for book, values in book_feed.items()
            #     if book not in existing_books
            # }

            new_books = {
                book: {
                    side: data
                    for side, data in values.items()
                    if side.lower() == key_checker.lower()
                       or key_checker.lower() in side.lower()
                }
                for book, values in book_feed.items()
            }

            if new_books:
                odds["book_feed"] = new_books
                valid_odds.append(odds)

        if valid_odds:

            matched_data.append({
                "league": event["league"],
                "start_date": event["start_date"],
                "event_name": event["event_name"],
                "odds": valid_odds
            })

        else:
            unmatched_data.append(event)

    return {
        "matched": matched_data,
        "unmatched": unmatched_data
    }


async def compare():

    # redis_instance = RedisAsyncManager(database=7)
    # bettorodds_redis_instance = RedisAsyncManager(database=13)
    #
    # novig = await redis_instance.get_data("novig")
    # prophetx = await redis_instance.get_data("prophetx")
    # # add more books here
    # # draftkings = await redis_instance.get_data("draftkings")
    #
    # books = {
    #     "Novig": novig,
    #     "Prophetx": prophetx,
    #     # "DraftKings": draftkings
    # }
    #
    # merged, unmatched = combine_books(books)
    #
    # with open("merged_NEW.json", "w") as f:
    #     json.dump(merged, f, indent=2)
    #
    # # Save unmatched per book
    # for book_name, data in unmatched.items():
    #
    #     filename = f"{book_name.lower()}_unmatched.json"
    #
    #     with open(filename, "w") as f:
    #         json.dump(data, f, indent=2)
    #
    #
    # raw_bettorodds = await bettorodds_redis_instance.get_data("bettoroddds_odds")
    # bettorodds = _reformat_bettorodds(raw_bettorodds)
    #
    # with open("bettorodds_NEW.json", "w") as f:
    #     json.dump(bettorodds, f, indent=2)

    with open("merged.json", "r") as file:
        merged_data = json.load(file)

    with open("bettorodds_3.json", "r") as file:
        bettorodds_data = json.load(file)

    data = add_book_feed(bettorodds_data=bettorodds_data, merged_data=merged_data)

    with open("final_merged.json", "w") as f:
        json.dump(data.get("matched"), f, indent=2)

    with open("final_unmatched.json", "w") as f:
        json.dump(data.get("unmatched"), f, indent=2)

asyncio.run(compare())