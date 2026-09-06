from fastapi import APIRouter, Request, Query, Depends
from typing import List, Optional
from API.Helpers.common import get_books
from API.Helpers.parlay_helper import ParlayFetcher, SGPBooks
from API.security import get_api_key
from Database.base_db import DB
from Database.AutoSGP.sgp_db import SGPHistory

router = APIRouter(prefix="/sgp", tags=["SGP"])

SPECIAL_MAPPING = {
    "hardrock": "hard rock",
    "onyxodds": "onyx odds",
    "prophetx": "prophet x",
    "propbuilder": "prop builder"
}

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

async def get_auto_sgp_data(request: Request, include_ev_data=False):
    redis_instance = request.app.state.redis.get("auto_sgp")
    sgp_data = await redis_instance.get_all_key_values()

    game_details = []

    for sgp in sgp_data:
        weighted_books = sgp.get("weighted_sgp_odds")
        book_list = [book for book in weighted_books.keys()]

        highest_ev = next(iter(weighted_books.values())).get("ev")
        best_book = next(iter(weighted_books.keys()))

        entry = {
            "game_key": sgp.get("game_key"),
            "event": sgp.get("event"),
            "date": sgp.get("date"),
            "league": sgp.get("league"),
            "sgp_odds": sgp.get("sgp_odds"),
            "median_books": sgp.get("median_met_books"),
            "sgp_links": sgp.get("sgp_links"),
            "fair_value": sgp.get("fair_value"),
            "game_keys": [game_key.get("id") for game_key in sgp.get("legs", [])],
            "individual_odds": sgp.get("individual_odds"),
            "time_fetched": sgp.get("time_fetched"),
            "weighted_fair_value": sgp.get("weighted_fair_value", {}),
            "highest_ev": highest_ev,
            "best_book": best_book,
            "book_list": book_list,
            "legs": sgp.get("legs", []),
        }

        game_details.append(entry)

    game_details = sorted(game_details, key=lambda x: x['highest_ev'], reverse=True)

    return game_details


def sgp_matches_filters(sgp, books=None, min_ev=None, leagues=None, best_book=None, exclusive_books=None,
                        min_books=None, max_ev=None):
    if books:
        books = [SPECIAL_MAPPING.get(book.lower(), book.lower()) for book in books]
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



@router.get("/auto_sgp/boost_book",
            summary="Get Auto SGP by book",
            description="Fetch Auto SGP odds based on a specific book.",
            dependencies=[Depends(get_api_key)]
            )
async def get_auto_sgp_by_book(
        request: Request,
        book: str = Query(..., description="Book to check Auto SGP's")
):
    sgp_data = await get_auto_sgp_data(request, include_ev_data=True)
    return [
        {
            **sgp,
            "book_ev": sgp.get("ev_data", {}).get(book.lower(), {}).get("ev")
        }
        for sgp in sgp_data
        if book.lower() in sgp["book_list"]
    ]

@router.get("/auto_sgp/history",
            summary="Get Auto SGP History",
            description="Fetch Auto SGP history.",
            dependencies=[Depends(get_api_key)]
            )
async def get_auto_sgp_history(db: DB):
    return await SGPHistory.all_history(db)



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
    books = [SPECIAL_MAPPING.get(book.lower(), book.lower()) for book in books] if books else None
    exclusive_books = [SPECIAL_MAPPING.get(book.lower(), book.lower()) for book in exclusive_books] if exclusive_books else None
    best_book = SPECIAL_MAPPING.get(best_book.lower(), best_book.lower()) if best_book else None
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