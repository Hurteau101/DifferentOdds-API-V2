import asyncio
import aiohttp
from fastapi import APIRouter, Request, Query, Depends
from openai import BaseModel
from typing import List, Optional
from collections import Counter
from API.Helpers.common import get_books, get_cached_books, get_redis_data
from API.security import get_api_key
from Books.SGP.betmgm_sgp import BetmgmSGP
from Books.SGP.betway_sgp import BetwaySGP
from Books.SGP.caesar_sgp import CaesarsSGP
from Books.SGP.draftkings_sgp import DraftkingsSGP
from Books.SGP.fanactics_sgp import FanaticsSGP
from Books.SGP.fanduel_sgp import FanduelSGP
from Books.SGP.hardrock_sgp import HardrockSGP
from Books.SGP.kambi_sgp import KambiSGP
from Books.SGP.novig_sgp import NovigSGP
from Books.SGP.onyx_sgp import OnyxSGP
from Books.SGP.prophetx_sgp import ProphetxSGP
from Books.SGP.thescore_sgp import ThescoreSGP
from curl_cffi import AsyncSession as CurlAsyncSession


router = APIRouter(prefix="/sgp", tags=["SGP"])

class SGPBooks(BaseModel):
    book_name: str
    links: list[str]
    lines: dict | None = None
    event_data: dict | None = None

DEFAULT_TIMEOUT = 15
DEFAULT_SESSION = "aiohttp"

BOOK_INITIALIZERS = {
    "fanduel": {
        "class": FanduelSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "betmgm": {
        "class": BetmgmSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "fanatics": {
        "class": FanaticsSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "kambi": {
        "class": KambiSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "draftkings": {
        "class": DraftkingsSGP,
        "session": "curl",
        "timeout": DEFAULT_TIMEOUT
    },
    "hardrock": {
        "class": HardrockSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "onyxodds": {
        "class": OnyxSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "prophetx": {
        "class": ProphetxSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "novig": {
        "class": NovigSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "thescore": {
        "class": ThescoreSGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    },
    "caesars": {
        "class": CaesarsSGP,
        "session": "curl",
        "timeout": DEFAULT_TIMEOUT
    },
    "betway": {
        "class": BetwaySGP,
        "session": DEFAULT_SESSION,
        "timeout": DEFAULT_TIMEOUT
    }
}

BOOK_CLASSES = {
    book: configs
    for book, configs in BOOK_INITIALIZERS.items()
    for cached_books in get_cached_books(book_type="sgp")
    if book in cached_books.get("book_key") and cached_books.get("status") == True
}


@router.get("/books_list",
            summary="Get SGP Books List",
            description="Retrieve a list of available SGP books.",
            )
async def get_book_list():
    return get_books(book_type="sgp")


@router.post("/odds",
            summary="Get SGP Odds",
            description="Fetch SGP odds from specified sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_sgp_odds(books: List[SGPBooks], request: Request):
    async def fetch_sgp_odds(book: SGPBooks, session_mapper: dict):
        book_configs = BOOK_CLASSES.get(book.book_name.lower())
        if not book_configs:
            return {}

        session = session_mapper.get(book_configs.get("session"))
        sgp_data = {
            "book_name": book.book_name.lower(),
            "links": book.links,
        }


        book_instance = book_configs.get("class")(
            sgp_data=sgp_data,
            mapped_ids_redis_instance=request.app.state.redis.get("sgp_mapped_ids"),
            auth_redis_instance=request.app.state.redis.get("sgp_auth")
        )
        try:
            odds = await asyncio.wait_for(book_instance.run_book(session=session), timeout=book_configs.get("timeout"))
            return {book.book_name: odds}

        except asyncio.TimeoutError:
            pass

    invalid_books = {
        book.book_name: None
        for book in books
        if book.book_name.lower() not in BOOK_CLASSES
    }

    async with CurlAsyncSession(impersonate="safari15_5") as curl_session, aiohttp.ClientSession() as aiohttp_session:
        session_mapper = {"curl": curl_session, "aiohttp": aiohttp_session}
        tasks = [fetch_sgp_odds(book, session_mapper) for book in books]
        results = await asyncio.gather(*tasks)

        merged = [
            {
                "book_name": book.book_name,
                "odds": result.get(book.book_name) if result else None,
                "links": book.links
            }
            for book, result in zip(books, results)
        ]

        book_occurrence = Counter(
            book_name
            for result in results
            for book_name, value in result.items()
        )

        odds_by_book = {}

        for merge in merged:
            book_name = merge.get("book_name")
            if book_occurrence[book_name] <= 1:
                odds_by_book[book_name] = merge.get("odds", None)
            else:
                odds_by_book.setdefault(book_name, []).append({
                    "odds": merge.get("odds"),
                    "links": merge.get("links")
                })

        for book_name, book_data in odds_by_book.items():
            if isinstance(book_data, list):
                all_null = all(entry.get("odds") is None for entry in book_data)
                if all_null:
                    odds_by_book[book_name] = None

        odds_by_book.update(invalid_books)
        return odds_by_book

async def get_auto_sgp_data(request: Request):
    redis_instance = request.app.state.redis.get("auto_sgp")
    sgp_data = await redis_instance.get_all_key_values()

    game_details = []

    for sgp in sgp_data:
        weighted_books = sgp.get("ev_results", {}).get("weighted_book_data")
        book_list = [book for book in weighted_books.keys()]

        sorted_books = sorted(
            weighted_books.items(),
            key=lambda kv: kv[1].get("ev", float("-inf")),
            reverse=True
        )

        highest_ev = sorted_books[0][1].get("ev") if sorted_books else None
        best_book = sorted_books[0][0] if sorted_books else None

        entry = {
            "game_key": sgp.get("redis_key"),
            "event": sgp.get("event"),
            "date": sgp.get("date"),
            "league": sgp.get("league"),
            "sgp_odds": sgp.get("filtered_sgp_odds"),
            "median_books": sgp.get("non_met_books"),
            "sgp_links": sgp.get("sgp_links"),
            "fair_value": sgp.get("fair_value"),
            "game_keys": sgp.get("game_keys", []),
            "individual_odds": sgp.get("filtered_individual_odds"),
            "time_fetched": sgp.get("time_fetched"),
            "weighted_fair_value": sgp.get("ev_results", {}).get("weighted_fair_value", None),
            "highest_ev": highest_ev,
            "best_book": best_book,
            "book_list": book_list,
            "legs": []
        }

        indices = {
            int(key.split("_")[-1])
            for key in sgp.keys()
            if key.startswith("stat_") and key.split("_")[-1].isdigit()
        }

        # Build each stat leg
        for i in sorted(indices):
            market_type = sgp.get(f"market_type_{i}")
            if market_type == "player":
                line = sgp.get(f"stat_type_{i}_line").split(" ")[-1].strip()
                player_name = " ".join(sgp.get(f"stat_type_{i}_line").split(" ")[:-1]).strip()
            elif market_type == "team":
                line = sgp.get(f"stat_type_{i}_line").split(" ")[-1].strip()
                player_name = None
            else:
                line = None
                player_name = None

            entry["legs"].append({
                "market_type": sgp.get(f"stat_name_{i}"),
                "line": float(line) if line else None,
                "direction": sgp.get(f"stat_{i}_direction"),
                "team": sgp.get(f"team_{i}"),
                "player_name": player_name,
            })

        game_details.append(entry)

    game_details = sorted(game_details, key=lambda x: x['highest_ev'], reverse=True)

    return game_details


def sgp_matches_filters(sgp, books=None, min_ev=None, leagues=None, best_book=None, exclusive_books=None,
                        min_books=None, max_ev=None):
    if books:
        if not (set(sgp["book_list"]) & set(books)):
            return False

    if exclusive_books:
        required_books = set(exclusive_books)
        if best_book:
            required_books.add(best_book.lower())

        if not all(book in [b.lower() for b in sgp["book_list"]] for book in required_books):
            return False


    if min_books:
        if len(sgp["book_list"]) < min_books:
            return False

    if max_ev is not None:
        if sgp["highest_ev"] > max_ev:
            return False

    if min_ev is not None:
        if sgp["highest_ev"] < min_ev:
            return False

    if leagues:
        if sgp["league"].lower() not in leagues:
            return False

    if best_book:
        if sgp["best_book"].lower() != best_book.lower():
            return False

    return True


@router.get("/auto_sgp",
            summary="Get the Auto SGP Odds",
            description="Fetch Auto SGP odds from all available sportsbooks.",
            dependencies=[Depends(get_api_key)]
            )
async def get_auto_sgp_odds(
        request: Request,
        books: Optional[List[str]] = Query(
            None,
            description="Optional list of books to match (ANY): include SGPs that contain at least one of these books"
        ),
        leagues: Optional[List[str]] = Query(
            None, description="Optional list of leagues that must be included in the SGP"
        ),
        min_ev: Optional[float] = Query(
            None, description="Optional Minimum EV required"
        ),
        max_results: int = Query(
            150, description="Optional Maximum number of results to return"
        ),
        best_book: Optional[str] = Query(
            None, description="Optional filter to only include SGPs where this book is the best book"
        ),
        exclusive_books: Optional[List[str]] = Query(
            None, description="Optional list of books that must all be included in the SGP"
        ),
        min_books: Optional[int] = Query(
            None, description="Optional minimum number of books that must be included in the SGP"
        ),
        max_ev: Optional[float] = Query(
            None, description="Optional Maximum EV allowed"
        ),
):
    books = [book.lower() for book in books] if books else None
    leagues = [l.lower() for l in leagues] if leagues else None
    sgp_data = await get_auto_sgp_data(request)

    results = [
        sgp for sgp in sgp_data
        if sgp_matches_filters(
            sgp,
            books=books,
            min_ev=min_ev,
            leagues=leagues,
            best_book=best_book,
            exclusive_books=exclusive_books,
            min_books=min_books,
            max_ev=max_ev
        )
    ]

    sorted_results = sorted(
        results,
        key=lambda x: max(x['sgp_odds'].values()),
        reverse=True
    )

    if not sorted_results:
        return []

    return sorted_results[:max_results]