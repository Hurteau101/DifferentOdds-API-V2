from fastapi import APIRouter, Depends
from API.security import get_api_key

router = APIRouter(prefix="/dfs", tags=["dfs"])

@router.get("/health", summary="Health Check", description="Check the health status of the DFS API.")
async def health_check():
    return {"status": "DFS API is healthy"}

@router.get(
    "/odds",
    summary="Get DFS Odds",
    description="Fetch the latest DFS odds from various sportsbooks.",
    dependencies=[Depends(get_api_key)]
)
async def get_dfs_odds():
    return {"message": "DFS odds data will be here"}