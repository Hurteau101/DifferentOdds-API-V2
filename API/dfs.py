import asyncio
from typing import List, Dict
from fastapi import Request

import orjson
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from API.security import get_api_key
from API.setup import create_logging_setup
from Redis.redis_manager import RedisManager
from Settings.sportsbook_config import SportsbookConfig
router = APIRouter(prefix="/dfs", tags=["DFS"])

# Set a timeout for fetching data from Redis
TIMEOUT_SECONDS = 5

file_logger = create_logging_setup(folder_name="dfs", file_name="dfs_api.log")

class Books(BaseModel):
    title: str
    book_key: str

class BooksListResponse(BaseModel):
    dfs_books: List[Books]

class BookParameters(BaseModel):
    book_nams: List[str]

# async def fetch_redis_data(key_name):
#     redis = RedisManager(db=0)
#     try:
#         cached_data = await redis.fetch_data(key_name)
#         if not cached_data:
#             return None
#
#         return orjson.loads(cached_data)
#
#     except Exception as e:
#         return None

# async def fetch_redis_data(key_name):
#     redis = RedisManager(db=0)
#     try:
#         cached_data = await redis.fetch_data(key_name)
#         if not cached_data:
#             return None
#
#         return cached_data
#
#     except Exception:
#         return None

async def fetch_redis_data(key_name, request):
    redis: RedisManager = request.app.state.redis
    try:
        return await redis.fetch_data(key_name)
    except Exception:
        return None

@router.get("/books_list",
            summary="Get DFS Books List",
            description="Retrieve a list of available DFS books.",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = SportsbookConfig.get_book_info(book_type="dfs")
    if not result:
        raise HTTPException(status_code=500, detail="No DFS books available. Please contact support.")

    return {"dfs_books": result}

@router.get(
    "/odds",
    summary="Get DFS Odds",
    dependencies=[Depends(get_api_key)]
)
async def get_book_data(
        request: Request,
        books: List[str] = Query(..., description="List of DFS book names to fetch data for"),
):
    dfs_books = [book.get("book_key") for book in SportsbookConfig.get_book_info(book_type="dfs")]
    for book in books:
        if book.lower() not in dfs_books:
            raise HTTPException(status_code=400, detail=f"Invalid book name: {book}")

    # Fetch data concurrently with timeout
    tasks = [
        asyncio.wait_for(fetch_redis_data(f"dfs:{book.lower()}", request), timeout=TIMEOUT_SECONDS)
        for book in books
    ]

    # Use return_exceptions=True to handle individual task failures
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Clean results, replacing exceptions with None
    clean_results = {}
    for book, result in zip(books, results):
        if isinstance(result, asyncio.TimeoutError):
            clean_results[book] = None
        elif isinstance(result, Exception):
            clean_results[book] = None
        else:
            clean_results[book] = result

    # clean_results = {}
    # for book, result in zip(books, results):
    #     if isinstance(result, (asyncio.TimeoutError, Exception)):
    #         clean_results[book] = None
    #     else:
    #         if isinstance(result, dict) and "payload" in result and "last_refresh" in result:
    #             clean_results[book] = {
    #                 "data": result["payload"],
    #                 "last_refresh": result["last_refresh"]
    #             }
    #         else:
    #             clean_results[book] = {
    #                 "data": result,
    #                 "last_refresh": None
    #             }

    # Final Check - if all results are None, raise 500 error
    if all(v is None for v in clean_results.values()):
        file_logger.log(
            message="No data available for the requested books.",
            books=",".join(books),
            level="ERROR"
        )
        raise HTTPException(status_code=500,
                            detail="No data available for the requested books. Please try again later.")

    return clean_results

