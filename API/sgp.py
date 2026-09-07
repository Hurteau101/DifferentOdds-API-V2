from datetime import datetime, UTC
from fastapi import APIRouter, Request, Query, Depends, HTTPException
from typing import List, Optional

from pydantic import AwareDatetime

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

def default_midnight():
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

def default_end_of_day():
    return datetime.now(UTC).replace(hour=23, minute=59, second=59, microsecond=999999)

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

def _convert_date_string(date_str: str):
    return datetime.fromisoformat(date_str)


def sgp_matches_filters(sgp, books=None, min_ev=None, leagues=None, best_book=None, exclusive_books=None,
                        min_books=None, max_ev=None, event_start_date=None, event_end_date=None, min_leg=None, max_leg=None):
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

    if event_start_date is not None:
        if all(_convert_date_string(leg["date"]) < event_start_date for leg in sgp["legs"]):
            return False

    if event_end_date is not None:
        if all(_convert_date_string(leg["date"]) > event_end_date for leg in sgp["legs"]):
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

    if min_leg is not None:
        if len(sgp["legs"]) <= min_leg:
            return False

    if max_leg is not None:
        if len(sgp["legs"]) >= max_leg:
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
async def get_auto_sgp_history(
        db: DB,
        date_from: AwareDatetime = Query(default_factory=default_midnight, description="Date to start fetching history from (UTC, ISO 8601 with offset | Example: 2026-09-05T13:30:00Z)"),
        date_to: AwareDatetime = Query(default_factory=default_end_of_day, description="Date to end fetching history from (UTC, ISO 8601 with offset | Example: 2026-09-05T13:30:00Z)"),
        league: Optional[str] = Query(None, description="Optional league to filter by"),
        event_name: Optional[str] = Query(None, description="Optional event name to filter by"),
        books: Optional[List[str]] = Query(None, description="Optional list of books to filter by"),
):
    days_difference = (date_to - date_from).days

    if days_difference > 30:
        raise HTTPException(status_code=422, detail="Date range must be less than 30 days")

    books = [SPECIAL_MAPPING.get(b.lower(), b.lower()) for b in books] if books else None

    return await SGPHistory.all_history(
        session=db,
        date_from=date_from,
        date_to=date_to,
        league=league,
        event_name=event_name,
        books=books
    )


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
        event_start_date: Optional[AwareDatetime] = Query(
            None, description="Optional event date to start fetching SGPs from (UTC, ISO 8601 with offset | Example: 2026-09-05T13:30:00Z)"
        ),
        event_end_date: Optional[AwareDatetime] = Query(
            None, description="Optional event date to end fetching SGPs from (UTC, ISO 8601 with offset | Example: 2026-09-05T13:30:00Z)"
        ),
        min_leg: Optional[int] = Query(
            None, description="Optional minimum number of legs that must be included in the SGP"
        ),
        max_leg: Optional[int] = Query(
            None, description="Optional maximum number of legs that must be included in the SGP"
        )


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
            max_ev=max_ev,
            event_start_date=event_start_date,
            event_end_date=event_end_date,
            min_leg=min_leg,
            max_leg=max_leg
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