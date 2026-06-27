import asyncio
import aiohttp
from fastapi import Request
from pydantic import BaseModel
from typing import List
from collections import Counter
from API.Helpers.common import get_cached_books
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

class SGPBooks(BaseModel):
    book_name: str
    links: list[str]
    lines: dict | None = None
    event_data: dict | list | None = None

class RFQParlay(BaseModel):
    book_name: str
    links: list[str]


class ParlayFetcher:
    """
    Fetches Parlay odds. Based on if `is_rfq` is True, will determine if the book will bypass SGP only odds,
    and fetch the regular parlay odds
    """
    def __init__(self, is_rfq: bool):
        self.default_timeout = 15
        self.default_session = "aiohttp"
        self.is_rfq = is_rfq
        self.books = self._load_books(filter_rfq=is_rfq)


    def _load_sgp_data(self, book: SGPBooks) -> dict:
        return {
            "book_name": book.book_name.lower(),
            "links": book.links,
            "event_data": book.event_data or [],
        }

    def _load_rfq_data(self, book: RFQParlay) -> dict:
        return {
            "book_name": book.book_name.lower(),
            "links": book.links,
            "is_sgp": False
        }

    def _load_books(self, filter_rfq: bool = False):
        books = {
            "fanduel": {
                "class": FanduelSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "betmgm": {
                "class": BetmgmSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "fanatics": {
                "class": FanaticsSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "kambi": {
                "class": KambiSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "draftkings": {
                "class": DraftkingsSGP,
                "session": "curl",
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "hardrock": {
                "class": HardrockSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "onyxodds": {
                "class": OnyxSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "prophetx": {
                "class": ProphetxSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": True
            },
            "novig": {
                "class": NovigSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": True
            },
            "thescore": {
                "class": ThescoreSGP,
                "session": self.default_session,
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "caesars": {
                "class": CaesarsSGP,
                "session": "curl",
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            },
            "betway": {
                "class": BetwaySGP,
                "session": "curl",
                "timeout": self.default_timeout,
                "has_rfq_parlay": False
            }
        }

        return {
            book: configs
            for book, configs in books.items()
            for cached_books in get_cached_books(book_type="sgp")
            if book in cached_books.get("book_key") and cached_books.get("status") == True
            and (not filter_rfq or configs["has_rfq_parlay"])
        }

    async def _call_book(self, book: SGPBooks | RFQParlay, session_mapper: dict, request: Request):
        book_configs = self.books.get(book.book_name.lower())
        if not book_configs:
            return {}

        session = session_mapper.get(book_configs.get("session"))
        sgp_data = self._load_sgp_data(book) if not self.is_rfq else self._load_rfq_data(book)

        book_instance = book_configs.get("class")(
            sgp_data=sgp_data,
            mapped_ids_redis_instance=request.app.state.redis.get("sgp_mapped_ids"),
            auth_redis_instance=request.app.state.redis.get("sgp_auth"),
        )
        try:
            odds = await asyncio.wait_for(book_instance.run_book(session=session), timeout=book_configs.get("timeout"))
            return {book.book_name: odds}

        except asyncio.TimeoutError:
            pass

    async def get_parlay_odds(self, books: List[SGPBooks] | List[RFQParlay], request: Request):
        invalid_books = {
            book.book_name: None
            for book in books
            if book.book_name.lower() not in self.books
        }

        async with CurlAsyncSession(impersonate="safari15_5") as curl_session, aiohttp.ClientSession() as aiohttp_session:
            session_mapper = {"curl": curl_session, "aiohttp": aiohttp_session}

            tasks = [self._call_book(
                book=book,
                session_mapper=session_mapper,
                request=request,
            ) for book in books]

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
                if result
                for book_name, value in result.items()
            )

            odds_by_book = {}

            for merge in merged:
                book_name: str = merge.get("book_name")
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


