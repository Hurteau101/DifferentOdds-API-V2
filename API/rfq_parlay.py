from fastapi import APIRouter, Request, Depends
from typing import List
from API.Helpers.parlay_helper import RFQParlay, ParlayFetcher
from API.security import get_api_key

router = APIRouter(prefix="/rfq_parlay", tags=["RFQ Parlay"])

@router.post("/odds",
            summary="Get RFQ Odds",
            description="Fetch RFQ Parlay odds from specified sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_rfq_odds(books: List[RFQParlay], request: Request):
    parlay_data = ParlayFetcher(is_rfq=True)
    return await parlay_data.get_parlay_odds(
        books=books,
        request=request
    )