from Redis.redis_manager import RedisAsyncManager
import json
import asyncio

def index_book(book_data):
    index = {}

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

        index[selection_key] = game

    return index

def intersect_books(index_a, index_b, name_a, name_b):
    found_data = {}


    common_games = index_a.keys() & index_b.keys()
    print(f"Total Matches: {len(common_games)}")

    for common in common_games:
        found_a = index_a[common]
        found_b = index_b[common]

        game_details = {
            "league": found_a["league"],
            "start_date": found_a["start_date"],
            "event_name": found_a["event_name"],
            # **found_a["selection_key"],
            # "odds": {
            #     name_a: found_a["liquidity_data"],
            #     name_b: found_b["liquidity_data"]
            # }
        }

        odds = {
            "market": found_a["selection_key"]["market"],
            # "event_name": found_a["selection_key"]["event_name"],
           "line": found_a["selection_key"]["line"],
           "bet_type": found_a["selection_key"]["bet_type"],
           "bet_team": found_a["selection_key"]["bet_team"],
           "bet_player": found_a["selection_key"]["bet_player"],
            name_a: found_a["liquidity_data"],
            name_b: found_b["liquidity_data"]
        }


        found_data.setdefault(found_a["event_name"], {
            **game_details,
            "odds": []
        })["odds"].append(odds)

    return list(found_data.values())

def find_unmatched(index_a, index_b):
    unmatched_keys = index_a.keys() - index_b.keys()
    return [index_a[key] for key in unmatched_keys]

async def compare():
    redis_instance = RedisAsyncManager(database=7)
    novig = await redis_instance.get_data("novig")
    prophetx = await redis_instance.get_data("prophetx")

    # with open("prophetx.json", "w") as f:
    #     json.dump(prophetx, f, indent=2)

    with open("novig.json", "w") as f:
        json.dump(novig, f, indent=2)

    novig_index = index_book(novig)
    prophetx_index = index_book(prophetx)

    data = intersect_books(novig_index, prophetx_index, "Novig", "Prophetx")

    with open("merged.json", "w") as f:
        json.dump(data, f, indent=2)

    novig_unmatched = find_unmatched(novig_index, prophetx_index)
    prophetx_unmatched = find_unmatched(prophetx_index, novig_index)

    with open("novig_unmatched.json", "w") as f:
        json.dump(novig_unmatched, f, indent=2)

    with open("prophetx_unmatched.json", "w") as f:
        json.dump(prophetx_unmatched, f, indent=2)

asyncio.run(compare())