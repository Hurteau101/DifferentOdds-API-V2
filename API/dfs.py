from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from API.security import get_api_key
from Settings.sportsbook_config import SportsbookConfig
router = APIRouter(prefix="/dfs", tags=["dfs"])

class Books(BaseModel):
    title: str
    book_key: str

class BooksListResponse(BaseModel):
    dfs_books: List[Books]

@router.get("/books_list",
            summary="Get DFS Books List",
            description="Retrieve a list of available DFS books.",
            response_model=BooksListResponse
            )
async def get_book_list():
    result = SportsbookConfig.get_dfs_names()  # returns {"dfs_books": [...]}
    if not result.get("dfs_books"):
        raise HTTPException(status_code=500, detail="No DFS books available. Please contact support.")

    return result


# @router.get("/health", summary="Health Check", description="Check the health status of the DFS API.")
# async def health_check():
#     return {"status": "DFS API is healthy"}
#
# @router.get(
#     "/odds",
#     summary="Get DFS Odds",
#     description="Fetch the latest DFS odds from various sportsbooks.",
#     dependencies=[Depends(get_api_key)]
# )
# async def get_dfs_odds():
#     return {"message": "DFS odds data will be here"}