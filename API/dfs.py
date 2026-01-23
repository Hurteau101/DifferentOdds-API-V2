from typing import List
from fastapi import APIRouter, Depends, Request, Query, Header
from API.Helpers.common import BooksListResponse, get_books, validate_format_header, get_book_odds, FormatHeader
from API.security import get_api_keys

router = APIRouter(prefix="/dfs", tags=["DFS"])


@router.get("/book_list",
            summary="DFS Books",
            description="Retrieve a list of supported DFS books",
            response_model=BooksListResponse
            )
async def get_book_list():
    return get_books(book_type="dfs")


@router.get(
    "/odds",
    summary="Get DFS Odds",
    dependencies=[Depends(get_api_keys)]
)
async def get_odds(
        request: Request,
        books: List[str] = Query(..., description="List of DFS book names to fetch data for"),
        fmt: FormatHeader = Depends(validate_format_header),
        dict_format: bool = Header(False, description="Return data in dictionary format", alias="X-Dict-Format")
):
    return await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="dfs",
        format_type=fmt.format,
        dict_format=dict_format
    )


