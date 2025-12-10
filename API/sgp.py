import asyncio
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from API.setup import create_logging_setup
from API.security import get_api_key
from SGP.betmgm import BetMGM_SGP
from SGP.draftkings import Draftkings_SGP
from SGP.fanactics import Fanatics_SGP
from SGP.fanduel import Fanduel_SGP
from SGP.hardrock import Hardrock_SGP
from SGP.kambi import Kambi_SGP
from SGP.novig import Novig_SGP
from SGP.onyx import Onyx_SGP
from SGP.prophet import Prophet_SGP
from Settings.sportsbook_config import SportsbookConfig
from Redis.redis_manager import RedisRemote

BOOK_INITIALIZERS = {
    "fanduel": Fanduel_SGP,
    "betmgm": BetMGM_SGP,
    "fanatics": Fanatics_SGP,
    "kambi": Kambi_SGP,
    "draftkings": Draftkings_SGP,
    "hardrock": Hardrock_SGP,
    "onyxodds": Onyx_SGP,
    "prophetx": Prophet_SGP,
    "novig": Novig_SGP,
}

file_logger = create_logging_setup(folder_name="sgp", file_name="sgp_api.log")

router = APIRouter(prefix="/sgp", tags=["SGP"])

class SGP(BaseModel):
    book_name: str
    links: List[str]

class Books(BaseModel):
    title: str
    book_key: str
    status: str

class BooksListResponse(BaseModel):
    sgp_books: List[Books]

@router.get("/books_list",
            summary="Get SGP Books List",
            description="Retrieve a list of available SGP books.",
            response_model=BooksListResponse
            )
async def get_sgp_book_list():
    result = SportsbookConfig.get_book_info(book_type="sgp")
    if not result:
        raise HTTPException(status_code=500, detail="No SGP books available. Please contact support.")

    return {"sgp_books": result}

@router.post("/odds",
                summary="Get SGP Odds",
                description="Fetch SGP odds from specified sportsbooks.",
                dependencies=[Depends(get_api_key)]
             )
async def get_sgp_odds(books: List[SGP]):
    # Create instance of each sportsbook and run concurrently
    async def fetch_sgp_odds(book, timeout=15, single_book=False):
        book_class = BOOK_INITIALIZERS.get(book.book_name.lower())
        if book_class:
            book_instance = book_class(links=book.links)
            try:
                return await asyncio.wait_for(book_instance.run_book(), timeout=timeout)
            except asyncio.TimeoutError:
                file_logger.log(sportsbook=book.book_name, message=f"{book.book_name} timed out", level="ERROR")

               # Single books we want to raise an error, for multiple just return the error in the response due to partial failure
                if single_book:
                    raise HTTPException(status_code=504, detail=f"{book.book_name} timed out")
                return None
            except Exception as e:
                return None

        return None

    sgp_books = [book.get("book_key") for book in SportsbookConfig.get_book_info(book_type="sgp")]

    for book in books:
        if book.book_name.lower() not in sgp_books:
            raise HTTPException(status_code=400, detail=f"Invalid sportsbook name: {book.book_name}")

    if len(books) > 1:
        # Run all fetch tasks concurrently
        tasks = [fetch_sgp_odds(book) for book in books]
        results = await asyncio.gather(*tasks)

        # Merge results with book names
        merged = {
            book.book_name: result
            for book, result in zip(books, results)
        }

        return merged
    else:
        # Single book, no need for concurrency
        result = await fetch_sgp_odds(books[0], single_book=True)
        return {books[0].book_name: result}


@router.get("/auto_sgp",
            summary="Get the Auto SGP Odds",
            description="Fetch Auto SGP odds from all available sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_auto_sgp():
    sgp_redis = RedisRemote()
    raw_data = sgp_redis.get_all_key_values()
    return raw_data
