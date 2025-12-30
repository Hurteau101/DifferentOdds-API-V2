import asyncio
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header, APIRouter
from typing import List, Optional, Literal
from pydantic import BaseModel
from API.common import get_cached_books, Books, validate_format_header
from API.security import get_api_key
from API.setup import create_logging_setup
from Settings.sportsbook_config import SportsbookConfig

file_logger = create_logging_setup(folder_name="prediction", file_name="prediction_api.log")

router = APIRouter(prefix="/prediction", tags=["Prediction"])
TIMEOUT_SECONDS = 5


class BooksListResponse(BaseModel):
    prediction_books: List[Books]


@router.get("/book_list",
            summary="Get Prediction Book List",
            description="Retrieve a list of available Prediction books.",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = get_cached_books(book_type="prediction")
    if not result:
        raise HTTPException(status_code=500, detail="No prediction books available. Please contact support.")

    return {"prediction_books": result}



async def get_odds(books, request, fmt):
    redis = request.app.state.redis.clone_with_db(1)

    prediction_books = [book.get("book_key") for book in SportsbookConfig.get_book_info(book_type="prediction")]
    for book in books:
        if book.lower() not in prediction_books:
            raise HTTPException(status_code=400, detail=f"Invalid book name: {book}")

    fmt = fmt.lower()
    tasks = [
        asyncio.wait_for(redis.fetch_data(f"prediction:{book.lower()}:{fmt}"), timeout=TIMEOUT_SECONDS)
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
        file_logger.log(
            sportsbook=",".join(books),
            message="No data available for the requested books.",
            books=",".join(books),
            level="ERROR"
        )
        raise HTTPException(status_code=500,
                            detail="No data available for the requested books. Please try again later.")

    return clean_results

@router.get(
    "/odds",
    summary="Get Prediction Odds",
    # dependencies=[Depends(get_api_key)]
    )
async def get_book_data(
        request: Request,
        books: List[str] = Query(..., description="List of Prediction book names to fetch data for"),
        fmt: str = Depends(validate_format_header)
):
    odds = await get_odds(books, request, fmt.format)
    return odds