from fastapi import APIRouter, Request, Query, Depends
from typing import List, Optional
from API.Helpers.common import get_books
from API.Helpers.parlay_helper import ParlayFetcher, SGPBooks
from API.security import get_api_key


router = APIRouter(prefix="/sgp", tags=["SGP"])


@router.get("/books_list",
            summary="Get SGP Books List",
            description="Retrieve a list of available SGP books.",
            )
async def get_book_list():
    return get_books(book_type="sgp")


@router.post("/odds",
            summary="Get SGP Odds",
            description="Fetch SGP odds from specified sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_sgp_odds(books: List[SGPBooks], request: Request):
    parlay_data = ParlayFetcher(is_rfq=False)
    return await parlay_data.get_parlay_odds(
        books=books,
        request=request
    )

async def get_auto_sgp_data(request: Request):
    redis_instance = request.app.state.redis.get("auto_sgp")
    sgp_data = await redis_instance.get_all_key_values()

    game_details = []

    for sgp in sgp_data:
        weighted_books = sgp.get("ev_results", {}).get("weighted_book_data")
        book_list = [book for book in weighted_books.keys()]

        sorted_books = sorted(
            weighted_books.items(),
            key=lambda kv: kv[1].get("ev", float("-inf")),
            reverse=True
        )

        highest_ev = sorted_books[0][1].get("ev") if sorted_books else None
        best_book = sorted_books[0][0] if sorted_books else None

        entry = {
            "game_key": sgp.get("redis_key"),
            "event": sgp.get("event"),
            "date": sgp.get("date"),
            "league": sgp.get("league"),
            "sgp_odds": sgp.get("filtered_sgp_odds"),
            "median_books": sgp.get("non_met_books"),
            "sgp_links": sgp.get("sgp_links"),
            "fair_value": sgp.get("fair_value"),
            "game_keys": sgp.get("game_keys", []),
            "individual_odds": sgp.get("filtered_individual_odds"),
            "time_fetched": sgp.get("time_fetched"),
            "weighted_fair_value": sgp.get("ev_results", {}).get("weighted_fair_value", None),
            "highest_ev": highest_ev,
            "best_book": best_book,
            "book_list": book_list,
            "legs": []
        }

        indices = {
            int(key.split("_")[-1])
            for key in sgp.keys()
            if key.startswith("stat_") and key.split("_")[-1].isdigit()
        }

        # Build each stat leg
        for i in sorted(indices):
            market_type = sgp.get(f"market_type_{i}")
            if market_type == "player":
                line = sgp.get(f"stat_type_{i}_line").split(" ")[-1].strip()
                player_name = " ".join(sgp.get(f"stat_type_{i}_line").split(" ")[:-1]).strip()
            elif market_type == "team":
                line = sgp.get(f"stat_type_{i}_line").split(" ")[-1].strip()
                player_name = None
            else:
                line = None
                player_name = None

            entry["legs"].append({
                "market_type": sgp.get(f"stat_name_{i}"),
                "line": float(line) if line else None,
                "direction": sgp.get(f"stat_{i}_direction"),
                "team": sgp.get(f"team_{i}"),
                "player_name": player_name,
            })

        game_details.append(entry)

    game_details = sorted(game_details, key=lambda x: x['highest_ev'], reverse=True)

    return game_details


def sgp_matches_filters(sgp, books=None, min_ev=None, leagues=None, best_book=None, exclusive_books=None,
                        min_books=None, max_ev=None):
    if books:
        if not (set(sgp["book_list"]) & set(books)):
            return False

    if exclusive_books:
        required_books = set(exclusive_books)
        if best_book:
            required_books.add(best_book.lower())

        if not all(book in [b.lower() for b in sgp["book_list"]] for book in required_books):
            return False


    if min_books:
        if len(sgp["book_list"]) < min_books:
            return False

    if max_ev is not None:
        if sgp["highest_ev"] > max_ev:
            return False

    if min_ev is not None:
        if sgp["highest_ev"] < min_ev:
            return False

    if leagues:
        if sgp["league"].lower() not in leagues:
            return False

    if best_book:
        if sgp["best_book"].lower() != best_book.lower():
            return False

    return True


@router.get("/auto_sgp",
            summary="Get the Auto SGP Odds",
            description="Fetch Auto SGP odds from all available sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_auto_sgp_odds(
        request: Request,
        books: Optional[List[str]] = Query(
            None,
            description="Optional list of books to match (ANY): include SGPs that contain at least one of these books"
        ),
        leagues: Optional[List[str]] = Query(
            None, description="Optional list of leagues that must be included in the SGP"
        ),
        min_ev: Optional[float] = Query(
            None, description="Optional Minimum EV required"
        ),
        max_results: int = Query(
            150, description="Optional Maximum number of results to return"
        ),
        best_book: Optional[str] = Query(
            None, description="Optional filter to only include SGPs where this book is the best book"
        ),
        exclusive_books: Optional[List[str]] = Query(
            None, description="Optional list of books that must all be included in the SGP"
        ),
        min_books: Optional[int] = Query(
            None, description="Optional minimum number of books that must be included in the SGP"
        ),
        max_ev: Optional[float] = Query(
            None, description="Optional Maximum EV allowed"
        ),
):
    books = [book.lower() for book in books] if books else None
    leagues = [l.lower() for l in leagues] if leagues else None
    sgp_data = await get_auto_sgp_data(request)

    results = [
        sgp for sgp in sgp_data
        if sgp_matches_filters(
            sgp,
            books=books,
            min_ev=min_ev,
            leagues=leagues,
            best_book=best_book,
            exclusive_books=exclusive_books,
            min_books=min_books,
            max_ev=max_ev
        )
    ]

    sorted_results = sorted(
        results,
        key=lambda x: max(x['sgp_odds'].values()),
        reverse=True
    )

    if not sorted_results:
        return []

    return sorted_results[:max_results]