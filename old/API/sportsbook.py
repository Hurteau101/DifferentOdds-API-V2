import asyncio
from fastapi import Depends, HTTPException, Query, Request, APIRouter
from typing import List
from pydantic import BaseModel
from old.API.common import get_cached_books, Books, validate_format_header
from old.API.security import get_api_key
from old.Settings.sportsbook_config import SportsbookConfig



router = APIRouter(prefix="/sportsbooks", tags=["sportsbooks"])

TIMEOUT_SECONDS = 5

class BooksListResponse(BaseModel):
    sportsbook_books: List[Books]

@router.get("/book_list",
            summary="Get Sportsbook List",
            description="Retrieve a list of available Sportsbooks",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = get_cached_books(book_type="sportsbooks")

    if not result:
        raise HTTPException(status_code=500, detail="No Sportsbooks available. Please contact support.")

    return {"sportsbook_books": result}


async def get_odds(books, request, fmt):
    redis = request.app.state.redis.clone_with_db(10)

    sportsbooks = [book.get("book_key") for book in SportsbookConfig.get_book_info(book_type="sportsbooks")]
    for book in books:
        if book.lower() not in sportsbooks:
            raise HTTPException(status_code=400, detail=f"Invalid book name: {book}")

    fmt = fmt.lower()
    tasks = [
        asyncio.wait_for(redis.fetch_data(f"sportsbook:{book.lower()}:{fmt}"), timeout=TIMEOUT_SECONDS)
        for book in books
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    clean_results = {}
    for book, result in zip(books, results):
        if isinstance(result, asyncio.TimeoutError):
            clean_results[book] = None
        elif isinstance(result, Exception):
            clean_results[book] = None
        else:
            clean_results[book] = result

    if all(v is None for v in clean_results.values()):
        raise HTTPException(status_code=500,
                            detail="No data available for the requested books. Please try again later.")

    return clean_results


@router.get(
    "/odds",
    summary="Get Sportsbook Odds",
    dependencies=[Depends(get_api_key)]
    )
async def get_book_data(
        request: Request,
        books: List[str] = Query(..., description="List of Sportbook names to fetch data for"),
        fmt: str = Depends(validate_format_header)
):
    odds = await get_odds(books, request, fmt.format)
    return odds