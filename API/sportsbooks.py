from typing import List
from fastapi import APIRouter, Depends, Request, Query, Header
from API.Helpers.common import BooksListResponse, get_books, validate_format_header, get_book_odds, FormatHeader
from API.security import get_api_keys

router = APIRouter(prefix="/sportsbooks", tags=["sportsbooks"])


@router.get("/book_list",
            summary="Sportsbooks",
            description="Retrieve a list of supported sportsbooks",
            response_model=BooksListResponse
            )
async def get_book_list():
    return get_books(book_type="sportsbooks")


@router.get(
    "/odds",
    summary="Get Sportsbooks Odds",
    dependencies=[Depends(get_api_keys)]
)
async def get_odds(
        request: Request,
        books: List[str] = Query(..., description="List of sportsbooks names to fetch data for"),
        fmt: FormatHeader = Depends(validate_format_header),
):
    return await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="sportsbooks",
        format_type=fmt.format,
    )
