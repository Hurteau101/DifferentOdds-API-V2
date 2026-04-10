import asyncio
from functools import lru_cache
from typing import Literal, Optional, List
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel
from Settings.book_configurations import BookConfiguration

FormatType = Literal["Base", "Game"]

class FormatHeader(BaseModel):
    format: Literal["Base", "Game"] = "Game"

class Books(BaseModel):
    title: str
    book_key: str
    status: bool

class BooksListResponse(BaseModel):
    books: List[Books]


@lru_cache(maxsize=5)
def get_cached_books(book_type: str) -> list[dict]:
    return BookConfiguration.get_book_info(book_type=book_type)


def get_books(book_type: str) -> BooksListResponse:
    """Retrieve a list of books for the specified book type."""
    books_info = get_cached_books(book_type=book_type)
    if not books_info:
        raise HTTPException(status_code=500, detail=f"No {book_type.title()} books available. Please try again later.")

    books = [Books(**book) for book in books_info]
    return BooksListResponse(books=books)


def validate_format_header(
    format: Optional[str] = Header(None, alias="X-Format", description="Select output format: Base or Game")
) -> FormatHeader:
    """Validate the X-Format header and return a FormatHeader instance."""
    value = (format or "Game").capitalize()

    if value not in ("Base", "Game"):
        raise HTTPException(
            status_code=422,
            detail="Invalid format. Must be one of: Base or Game."
        )
    return FormatHeader(format=value)

async def get_book_odds(request: Request, passed_in_books: list, book_type: str, format_type: str, timeout: int = 5, dict_format: bool = False):
    """Helper function to get odds for multiple books concurrently with timeout handling."""
    books = [book.get("book_key") for book in get_cached_books(book_type=book_type)]
    for book in passed_in_books:
        if book.lower() not in books:
            raise HTTPException(status_code=400, detail=f"Invalid book name: {book}")

    format = format_type.lower()


    tasks = [
        get_redis_data(
            request,
            redis_name=book_type.lower(),
            redis_key=f"{book.lower()}:{format}",
            timeout=timeout,
        )
        for book in passed_in_books
    ]

    # Use return_exceptions=True to handle individual task failures
    results = await asyncio.gather(*tasks, return_exceptions=True)

    cleaned_results = {}

    for book, result in zip(passed_in_books, results):
        if dict_format:
            if format.startswith("base") and isinstance(result, dict):
                items = result.get("data", [])
            else:
                items = result if isinstance(result, list) else []

            cleaned_results[book] = (
                {
                    data.get("game_key"): {
                        "league": data.get("league"),
                        "start_date": data.get("start_date"),
                        "teams": [{
                            "team_a": data.get("team_data", {}).get("team_a"),
                            "team_a_abbreviation": data.get("team_data", {}).get("team_a_abbreviation"),
                            "team_b": data.get("team_data", {}).get("team_b"),
                            "team_b_abbreviation": data.get("team_data", {}).get("team_b_abbreviation"),
                        }],
                        "solo_game": data.get("odds", [])[0].get("solo_game", False),
                        "combo": data.get("odds", [])[0].get("combo", False),
                        "future": data.get("odds", [])[0].get("future", False),
                        "odds": [
                            {
                                "player_name": f'Player {odds.get("player_name")}' if odds.get("player_name") and 'player' not in odds.get('player_name', '').lower() else odds.get("player_name", None),
                                "player_team": odds.get("player_team"),
                                "stat_type": odds.get("stat_type"),
                                "line": odds.get("line"),
                                "player_id": odds.get("optional_stats", {}).get("player_id"),
                                "bet_type": odds.get("bet_type"),
                                "regular_line": odds.get("regular_line"),
                                "market_type": odds.get("optional_stats", {}).get("market_type"),
                                "odds_type": odds.get("optional_stats", {}).get("odds_type"),
                                "multiplier": odds.get("optional_stats", {}).get("multiplier", 1.0),
                                "betlink": odds.get("optional_stats", {}).get("betlink"),
                                "odds": odds.get("odds_format", {}) if odds and odds.get("odds_format") else None,
                            }

                            for odds in data.get("odds", [])
                        ]

                    }
                    for data in items
                    if data and data.get("odds", [])
                }
            )
        else:
            cleaned_results[book] = result if isinstance(result, (list, dict)) else []


    return cleaned_results


async def get_redis_data(request: Request, redis_name: str, redis_key: str, timeout: int = 5):
    """Helper function to get data from Redis with a timeout."""
    redis = request.app.state.redis.get(redis_name)

    if redis is None:
        raise RuntimeError(f"Redis instance '{redis_name}' not found in application state.")

    try:
        return await asyncio.wait_for(redis.get_data(redis_key), timeout=timeout)
    except asyncio.TimeoutError:
        return None