import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel
from API.common import FormatHeader, validate_format_header, Books, get_cached_books
from API.security import get_api_key
from Redis.redis_manager import RedisManager
from Settings.sportsbook_config import SportsbookConfig

router = APIRouter(prefix="/liquidity", tags=["Liquidity"])
TIMEOUT_SECONDS = 5


class BooksListResponse(BaseModel):
    liquidity_books: List[Books]


@router.get("/book_list",
            summary="Get Liquidity Book List",
            description="Retrieve a list of available Liquidity books.",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = get_cached_books(book_type="liquidity")
    if not result:
        raise HTTPException(status_code=500, detail="No PPH books available. Please contact support.")

    return {"liquidity_books": result}


async def get_redis_liquidity(request):
    redis = request.app.state.redis.clone_with_db(4)
    return await redis.fetch_data("liquidity_data")
    if not liquidity_data:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    clean_results = {}
    for book, result in zip(books, results):
        if isinstance(result, asyncio.TimeoutError):
            clean_results[book] = None
        elif isinstance(result, Exception):
            clean_results[book] = None
        else:
            clean_results[book] = result

    return clean_results


def liquidity_matches_filters(liquidity_data, leagues=None, min_liquidity=None, max_liquidity=None, min_difference_amount=None, max_difference_amount=None):
    def grab_total_liquidity(liquidity_data):
        return max(
            side["total_liquidity"]
            for outcome in liquidity_data.get("outcomes", {}).values()
            for side in outcome
        )

    if leagues:
        if liquidity_data["league"].lower() not in leagues:
            return False

    if min_liquidity:
        highest_liquidity = grab_total_liquidity(liquidity_data)

        if highest_liquidity < min_liquidity:
            return False

    if max_liquidity:
        highest_liquidity = grab_total_liquidity(liquidity_data)

        if highest_liquidity > max_liquidity:
            return False

    if min_difference_amount:
        if liquidity_data.get("liquidity_difference", 0) < min_difference_amount:
            return False

    if max_difference_amount:
        if liquidity_data.get("liquidity_difference", 0) > max_difference_amount:
            return False

    return True




@router.get("/odds",
            summary="Get Liquidity Odds",
            description="Fetch Liquidity odds from specified sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )

async def get_liquidity_data(
        request: Request,
        books: Optional[List[str]] = Query(
            None, description="Optional list of books to match (ANY): include liquidity that contain at least one of these books"
        ),
        leagues: Optional[List[str]] = Query(
            None, description="Optional list of leagues that must be included in liquidity data"
        ),
        min_liquidity: Optional[float] = Query(
            None, description="Optional Minimum total liquidity allowed"
        ),
        max_liquidity: Optional[float] = Query(
            None, description="Optional Maximum total liquidity allowed"
        ),
        max_difference: Optional[float] = Query(
            None, description="Optional Maximum total difference allowed"
        ),
        min_difference: Optional[float] = Query(
            None, description="Optional Minimum total difference allowed"
        ),
        max_results: int = Query(
            150, description="Optional Maximum number of results to return"
        ),

):

    books = [book.lower() for book in books] if books else None
    leagues = [league.lower() for league in leagues] if leagues else None
    raw_odds = await get_redis_liquidity(books, request)
    if not raw_odds:
        return []

    filtered_books = [
        odds
        for odds in raw_odds
        if odds
        if odds.get("book_name").lower() in books
    ]

    results = [
        liquidity for liquidity in filtered_books
        if liquidity_matches_filters(
            liquidity_data=liquidity,
            leagues=leagues,
            min_liquidity=min_liquidity,
            max_liquidity=max_liquidity,
            max_difference_amount=max_difference,
            min_difference_amount=min_difference

        )
    ]

    return results[:max_results]

