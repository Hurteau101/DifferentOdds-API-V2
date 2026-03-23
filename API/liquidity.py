from typing import List
from fastapi import APIRouter, Depends, Request, Query, Header
from API.Helpers.common import BooksListResponse, get_books, validate_format_header, get_book_odds, FormatHeader, \
    get_redis_data
from API.security import get_api_keys

router = APIRouter(prefix="/liquidity", tags=["Liquidity"])

@router.get("/book_list",
            summary="DFS Books",
            description="Retrieve a list of supported Liquidity books",
            response_model=BooksListResponse
            )
async def get_book_list():
    return get_books(book_type="prediction_liquidity")


@router.get(
    "/odds",
    summary="Get Liquidity Odds",
    dependencies=[Depends(get_api_keys)]
)
async def get_odds(
        request: Request,
        books: List[str] = Query(..., description="List of liquidity book names to fetch data for"),
        fmt: FormatHeader = Depends(validate_format_header),
):
    return await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="prediction_liquidity",
        format_type=fmt.format,
    )

@router.get(
    "/compare",
    summary="Compare Liquidity Odds",
    dependencies=[Depends(get_api_keys)]
)
async def get_odds(
        request: Request,
):
    return await get_redis_data(
        request,
        redis_name="prediction_liquidity",
        redis_key="liquidity_comparison",
        timeout=10
    ) or []

