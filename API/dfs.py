import asyncio
from typing import List, Dict, Literal, Optional
from fastapi import Request, Header
from API.Formatters.dfs_formatter import get_formatter
import orjson
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from API.security import get_api_key
from API.setup import create_logging_setup
from Redis.redis_manager import RedisManager
from Settings.sportsbook_config import SportsbookConfig
from API.Esports.dfs_esports_filter import Esports
router = APIRouter(prefix="/dfs", tags=["DFS"])

# Set a timeout for fetching data from Redis
TIMEOUT_SECONDS = 5

file_logger = create_logging_setup(folder_name="dfs", file_name="dfs_api.log")

class Books(BaseModel):
    title: str
    book_key: str
    status: str

class BooksListResponse(BaseModel):
    dfs_books: List[Books]

class BookParameters(BaseModel):
    book_nams: List[str]

class FormatHeader(BaseModel):
    format: Literal["Base", "Game"] = "Game"

def validate_format_header(
    format: Optional[str] = Header(None, alias="X-Format", description="Select output format: Base or Game")
):
    format = (format or "Game").capitalize()

    if format not in ["Base", "Game"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be one of: Base or Game."
        )

    return FormatHeader(format=format)

async def get_odds(books, request):
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
        fmt: str = Depends(validate_format_header)
):
    odds = await get_odds(books, request)

    if fmt.format == "Game":
        return get_formatter("game", odds)


    return odds

@router.get(
    "/esport_lines",
    summary="Get Esports DFS Lines",
    dependencies=[Depends(get_api_key)]
)
async def get_esport_lines(
        request: Request,
        books: List[str] = Query(..., description="Get a list of esports DFS lines from specified books"),
):
    odds = await get_odds(books, request)
    esports = Esports(odds)
    return esports.get_esport_lines()


@router.get(
    "/esport_lines/differences",
    summary="Get Esports Difference Lines",
    dependencies=[Depends(get_api_key)]
)
async def get_esport_differences(
        request: Request,
        books: List[str] = Query(..., description="Get a list of esports DFS differences where multiple books have the same stat type"),
):
    if len(books) <= 1:
        raise HTTPException(status_code=400, detail="At least two books must be provided to compare differences.")

    odds = await get_odds(books, request)
    esports = Esports(odds)
    esport_lines = esports.get_esport_lines()
    if esport_lines:
        differences = esports.create_differences(esport_lines)
        if not differences:
            raise HTTPException(status_code=404, detail="No differences found between the provided books.")
    else:
        raise HTTPException(status_code=404, detail="No esports lines found for the provided books.")

    return differences