import asyncio
import json
from Redis.redis_manager import RedisAsyncManager

# def index_book(book_data):
#     index = {}
#
#     for game in book_data:
#         game_bucket = index.setdefault(game.get("game_key"), {
#             "event_name": game.get("event_name"),
#             "league": game.get("league"),
#             "start_date": game.get("start_date"),
#             "team_data": game.get("team_data"),
#             "selections": {}
#         })
#
#         for stat in game.get("odds"):
#             game_bucket["selections"].setdefault(stat.get("selection_id"), []).append(stat.get("odds"))
#
#     return index

# def index_book(book_data):
#     index = {}
#
#     for game in book_data:
#         game_bucket = index.setdefault(game["game_key"], {
#             "event_name": game["event_name"],
#             "league": game["league"],
#             "start_date": game["start_date"],
#             "team_data": game["team_data"],
#             "selections": {}
#         })
#
#         for stat in game["odds"]:
#             sk = stat.get("selection_key")
#             if not sk:
#                 continue
#
#             selection_id = (
#                 sk.get("market"),
#                 sk.get("line"),
#                 sk.get("side"),
#                 sk.get("team"),
#                 sk.get("player"),
#             )
#
#             for liq in stat.get("liquidity_data", []):
#                 game_bucket["selections"].setdefault(selection_id, {
#                     "selection": sk,
#                     "offers": []
#                 })["offers"].append(liq)
#
#     return index
#
# def intersect_books(index_a, index_b, name_a, name_b):
#     merged = {}
#
#     # --- GAME INTERSECTION ---
#     common_games = index_a.keys() & index_b.keys()
#
#     for gk in common_games:
#         game_a = index_a[gk]
#         game_b = index_b[gk]
#
#         sel_a = game_a["selections"]
#         sel_b = game_b["selections"]
#
#         # --- SELECTION INTERSECTION ---
#         common_selections = sel_a.keys() & sel_b.keys()
#
#         if not common_selections:
#             continue
#
#         merged[gk] = {
#             "event_name": game_a["event_name"],
#             "league": game_a["league"],
#             "start_date": game_a["start_date"],
#             "team_data": game_a["team_data"],
#             "odds": []
#         }
#
#         for sk in common_selections:
#             data_a = sel_a[sk]
#             data_b = sel_b[sk]
#
#             selection_info = data_a["selection"]
#
#             offers_a = data_a["offers"]
#             offers_b = data_b["offers"]
#
#             merged[gk]["odds"].append({
#                 **selection_info,
#                 name_a: offers_a,
#                 name_b: offers_b
#             })
#             #
#             # merged[gk]["odds"].append({
#             #     "selection": selection_info,
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#
#             # merged["odds"].append({
#             #     ""
#             # })
#
#
#             # merged[gk]["odds"][].append({
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#             # merged[gk]["selections"].append({
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#     return merged
#
#
# async def compare():
#     redis_instance = RedisAsyncManager(database=1)
#     novig = await redis_instance.get_data("novig:game")
#
#     prophetx = await redis_instance.get_data("prophetx:game")
#
#     with open("novig.json", "w") as f:
#         json.dump(novig, f, indent=2)
#
#     with open("prophetx.json", "w") as f:
#         json.dump(prophetx, f, indent=2)
#
#     novig_index = index_book(novig)
#
#     prophet_index = index_book(prophetx)
#
#     data = intersect_books(novig_index, prophet_index, "Novig", "Prophetx")
#     with open("merged.json", "w") as f:
#         json.dump(data, f, indent=2)
#
#
#
# if __name__ == "__main__":
#     asyncio.run(compare())


#
# ### MAYBE DON'T GROUP EVERYTHING TOGETHER.
#
import asyncio

from Books.Prediction_Liquidity.novig import Novig
from Books.Prediction_Liquidity.prophetx import Prophetx
import json


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


# def intersect_books(index_a, index_b, name_a, name_b):
#     found_data = []
#
#     common_games = index_a.keys() & index_b.keys()
#
#     for common in common_games:
#         found_a = index_a[common]
#         found_b = index_b[common]
#
#         game_details = {
#             "league": found_a["league"],
#             "start_date": found_a["start_date"],
#             "event_name": found_a["event_name"],
#             **found_a["selection_key"],
#             "odds": {
#                 name_a: found_a["liquidity_data"],
#                 name_b: found_b["liquidity_data"]
#             }
#         }
#
#         found_data.append(game_details)
#
#     return found_data

def intersect_books(index_a, index_b, name_a, name_b):
    found_data = {}


    common_games = index_a.keys() & index_b.keys()

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








async def compare():
    # novig = Novig()
    # prophetx = Prophetx()
    #
    # novig_data = await novig.run_book()
    # # prophetx_data = await prophetx.run_book()
    #
    #
    # nba_data = [
    #     data
    #     for data in novig_data
    #     if data.get("league") == "NBA"
    # ]
    #
    # with open("novig_data.json", "w") as f:
    #     json.dump(nba_data, f, indent=2)


    with open("../../delete_after/prophetx_data.json", "r") as f:
        novig_data = json.load(f)

    with open("../../delete_after/novig_data.json", "r") as f:
        prophetx_data = json.load(f)

    novig_index = index_book(novig_data)
    prophetx_index = index_book(prophetx_data)

    data = intersect_books(novig_index, prophetx_index, "Novig", "Prophetx")

    with open("merged_NEW.json", "w") as f:
        json.dump(data, f, indent=2)

    # safe_test = {str(k): v for k, v in novig_index.items()}
    # print(novig_index)
    # with open("test.json", "w") as f:
    #     json.dump(safe_test, f, indent=2, default=str)



# asyncio.run(compare())
async def test():
    redis_instance = RedisAsyncManager(database=7)
    data = await redis_instance.get_data("novig")

    with open("novig_change.json", "w") as f:
        json.dump(data, f, indent=2)

asyncio.run(test())










##############

# import asyncio
# import json
#
# from Books.Prediction_Liquidity.Old_Refactor_Testing.novig import Novig
# from Books.Prediction_Liquidity.Old_Refactor_Testing.prophetx import Prophetx
#
# def index_book(book_data):
#     index = {}
#
#     for game in book_data:
#         game_bucket = index.setdefault(game.game_key, {
#             "event_name": game.event_name,
#             "league": game.league,
#             "start_date": game.start_date,
#             "team_data": game.team_data,
#             "selections": {}
#         })
#
#         for stat in game.odds:
#             for ld in stat.liquidity_data:
#                 sk = ld.selection_key
#
#                 game_bucket["selections"].setdefault(sk, []).append(ld)
#
#     return index
#
#
# def intersect_books(idx_a, idx_b, name_a, name_b):
#     merged = {}
#
#     common_games = idx_a.keys() & idx_b.keys()
#
#     for gk in common_games:
#         game_a = idx_a[gk]
#         game_b = idx_b[gk]
#
#         sel_a = game_a["selections"]
#         sel_b = game_b["selections"]
#
#         common_selections = sel_a.keys() & sel_b.keys()
#
#         if not common_selections:
#             continue
#
#         merged[gk] = {
#             "event_name": game_a["event_name"],
#             "league": game_a["league"],
#             "start_date": game_a["start_date"],
#             "team_data": game_a["team_data"],
#             "selections": []
#         }
#
#         for sk in common_selections:
#             odds_a = sel_a[sk]
#             odds_b = sel_b[sk]
#
#             merged[gk]["selections"].append({
#                 name_a: odds_a,
#                 name_b: odds_b
#             })
#
#     return merged
#
#
#
# async def compare():
#
#     prophet_book = Prophetx()
#     novig_book = Novig()
#
#     prophet_data = await prophet_book.run_book()
#     novig_data = await novig_book.run_book()
#
#     idx_prophet = index_book(prophet_data)
#     idx_novig = index_book(novig_data)
#
#     # serialize = [asdict(d) for d in idx_prophet]
#     # with open("prophet_index.json", "w") as f:
#     #     json.dump(serialize, f, indent=2)
#
#     merged = intersect_books(
#         idx_novig,
#         idx_prophet,
#         "novig",
#         "prophetx"
#     )
#
#     print(json.dumps(merged, indent=2, default=str))
#
#     #
#     # with open("merged.json", "w") as f:
#     #     json.dump(serialize_merged(merged), f, indent=2)
#     #
#     # print(f"Common games: {len(merged)}")
#
# if __name__ == "__main__":
#     asyncio.run(compare())

###
#
# import asyncio
# import json
# from Redis.redis_manager import RedisAsyncManager
#
# # def index_book(book_data):
# #     index = {}
# #
# #     for game in book_data:
# #         game_bucket = index.setdefault(game.get("game_key"), {
# #             "event_name": game.get("event_name"),
# #             "league": game.get("league"),
# #             "start_date": game.get("start_date"),
# #             "team_data": game.get("team_data"),
# #             "selections": {}
# #         })
# #
# #         for stat in game.get("odds"):
# #             game_bucket["selections"].setdefault(stat.get("selection_id"), []).append(stat.get("odds"))
# #
# #     return index
#
# def index_book(book_data):
#     index = {}
#
#     for game in book_data:
#         game_bucket = index.setdefault(game["game_key"], {
#             "event_name": game["event_name"],
#             "league": game["league"],
#             "start_date": game["start_date"],
#             "team_data": game["team_data"],
#             "selections": {}
#         })
#
#         for stat in game["odds"]:
#             sk = stat.get("selection_key")
#             if not sk:
#                 continue
#
#             selection_id = (
#                 sk.get("market"),
#                 sk.get("line"),
#                 sk.get("side"),
#                 sk.get("team"),
#                 sk.get("player"),
#             )
#
#             for liq in stat.get("liquidity_data", []):
#                 game_bucket["selections"].setdefault(selection_id, {
#                     "selection": sk,
#                     "offers": []
#                 })["offers"].append(liq)
#
#     return index
#
# def intersect_books(index_a, index_b, name_a, name_b):
#     merged = {}
#
#     # --- GAME INTERSECTION ---
#     common_games = index_a.keys() & index_b.keys()
#
#     for gk in common_games:
#         game_a = index_a[gk]
#         game_b = index_b[gk]
#
#         sel_a = game_a["selections"]
#         sel_b = game_b["selections"]
#
#         # --- SELECTION INTERSECTION ---
#         common_selections = sel_a.keys() & sel_b.keys()
#
#         if not common_selections:
#             continue
#
#         merged[gk] = {
#             "event_name": game_a["event_name"],
#             "league": game_a["league"],
#             "start_date": game_a["start_date"],
#             "team_data": game_a["team_data"],
#             "odds": []
#         }
#
#         for sk in common_selections:
#             data_a = sel_a[sk]
#             data_b = sel_b[sk]
#
#             selection_info = data_a["selection"]
#
#             offers_a = data_a["offers"]
#             offers_b = data_b["offers"]
#
#             merged[gk]["odds"].append({
#                 **selection_info,
#                 name_a: offers_a,
#                 name_b: offers_b
#             })
#             #
#             # merged[gk]["odds"].append({
#             #     "selection": selection_info,
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#
#             # merged["odds"].append({
#             #     ""
#             # })
#
#
#             # merged[gk]["odds"][].append({
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#             # merged[gk]["selections"].append({
#             #     name_a: odds_a,
#             #     name_b: odds_b
#             # })
#
#     return merged
#
#
# async def compare():
#     redis_instance = RedisAsyncManager(database=1)
#     novig = await redis_instance.get_data("novig:game")
#
#     prophetx = await redis_instance.get_data("prophetx:game")
#
#     with open("novig.json", "w") as f:
#         json.dump(novig, f, indent=2)
#
#     with open("prophetx.json", "w") as f:
#         json.dump(prophetx, f, indent=2)
#
#     novig_index = index_book(novig)
#
#     prophet_index = index_book(prophetx)
#
#     data = intersect_books(novig_index, prophet_index, "Novig", "Prophetx")
#     with open("merged.json", "w") as f:
#         json.dump(data, f, indent=2)
#
#
#
# if __name__ == "__main__":
#     asyncio.run(compare())



