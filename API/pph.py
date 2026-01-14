import asyncio
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header, APIRouter
from typing import List, Optional, Literal
from pydantic import BaseModel
from API.security import get_api_key
from API.setup import create_logging_setup
from Settings.sportsbook_config import SportsbookConfig

router = APIRouter(prefix="/pph", tags=["PPH"])

TIMEOUT_SECONDS = 5

#### WILL BE REMOVING THIS FILE


class Books(BaseModel):
    title: str
    book_key: str
    status: str


class BooksListResponse(BaseModel):
    pph_books: List[Books]


class BookParameters(BaseModel):
    book_nams: List[str]

class FormatHeader(BaseModel):
    format: Literal["Base", "Game"] = "Game"

file_logger = create_logging_setup(folder_name="pph", file_name="pph_api.log")

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

@lru_cache(maxsize=None)
def get_cached_pph_books():
    return SportsbookConfig.get_book_info(book_type="pph")


@router.get("/book_list",
            summary="Get PPH Book List",
            description="Retrieve a list of available PPH books.",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = get_cached_pph_books()
    if not result:
        raise HTTPException(status_code=500, detail="No PPH books available. Please contact support.")

    return {"pph_books": result}


async def get_odds(books, request, fmt):
    redis = request.app.state.redis.clone_with_db(6)

    pph_books = [book.get("book_key") for book in SportsbookConfig.get_book_info(book_type="pph")]
    for book in books:
        if book.lower() not in pph_books:
            raise HTTPException(status_code=400, detail=f"Invalid book name: {book}")

    fmt = fmt.lower()
    tasks = [
        asyncio.wait_for(redis.fetch_data(f"pph:{book.lower()}:{fmt}"), timeout=TIMEOUT_SECONDS)
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
    summary="Get PPH Odds",
    dependencies=[Depends(get_api_key)]
    )
async def get_book_data(
        request: Request,
        books: List[str] = Query(..., description="List of DFS book names to fetch data for"),
        fmt: str = Depends(validate_format_header)
):
    odds = await get_odds(books, request, fmt.format)
    return odds