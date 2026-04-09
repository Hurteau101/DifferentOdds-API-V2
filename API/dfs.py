from typing import List
from fastapi import APIRouter, Depends, Request, Query, Header, HTTPException
from API.Esports.dfs_esports_filter import extract_esport_lines, create_differences
from API.Helpers.common import BooksListResponse, get_books, validate_format_header, get_book_odds, FormatHeader
from API.security import get_api_key

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
    dependencies=[Depends(get_api_key)]
)
async def get_odds(
        request: Request,
        books: List[str] = Query(..., description="List of DFS book names to fetch data for"),
        fmt: FormatHeader = Depends(validate_format_header),
        dict_format: bool = Header(True, description="Return data in dictionary format", alias="X-Dict-Format"),
):
    return await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="dfs",
        format_type=fmt.format,
        dict_format=dict_format
    )


@router.get(
    "/esport_lines",
    summary="Get Esports DFS Lines",
    dependencies=[Depends(get_api_key)]
)
async def get_esport_lines(
        request: Request,
        books: List[str] = Query(..., description="List of DFS book names to fetch data for"),
):
    odds = await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="dfs",
        format_type="base",
        dict_format=True
    )

    esports = extract_esport_lines(odds)

    if not esports:
        raise HTTPException(status_code=404, detail="No esports lines found for the provided books.")
    return esports

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

    odds = await get_book_odds(
        request=request,
        passed_in_books=books,
        book_type="dfs",
        format_type="game",
        dict_format=True
    )

    esports_lines = extract_esport_lines(odds)

    if not esports_lines:
        raise HTTPException(status_code=404, detail="No esports lines found for the provided books.")


    differences = create_differences(esports_lines)

    if not differences:
        raise HTTPException(status_code=404, detail="No differences found between the provided books.")


    return differences