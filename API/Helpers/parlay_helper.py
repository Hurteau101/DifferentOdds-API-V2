import asyncio
import importlib

import aiohttp
from fastapi import Request
from pydantic import BaseModel
from typing import List
from collections import Counter
from curl_cffi import AsyncSession as CurlAsyncSession
from API.Helpers.common import SPECIAL_MAPPING
from Settings.book_configurations import BookConfiguration


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
        book_config = BookConfiguration.get_book_info(
            book_type="sgp",
            remove_non_active=True,
            key_names={"name": "book_key", "class_name": "class_name", "class_path": "class_path", "curl_impersonation": "impersonate", "is_rfq_book":"is_rfq_book"}
        )

        return {
            book.get("book_key"): book
            for book in book_config
            if not filter_rfq or book.get("is_rfq_book", False)
        }


    async def _call_book(self, book: SGPBooks | RFQParlay, request: Request):
        book_config = self.books.get(book.book_name.lower())
        if not book_config:
            return {}

        async with CurlAsyncSession(impersonate=book_config.get("impersonate", "chrome")) as session:
            sgp_data = self._load_rfq_data(book) if self.is_rfq else self._load_sgp_data(book)

            module = importlib.import_module(book_config.get("class_path"))
            my_class = getattr(module, book_config.get("class_name"))

            class_instance = my_class(sgp_data=sgp_data)

            try:
                odds = await asyncio.wait_for(
                    class_instance.run_book(session=session),
                    timeout=book_config.get("timeout", self.default_timeout),
                )
                return {book.book_name: odds}
            except asyncio.TimeoutError:
                return None

    async def get_parlay_odds(self, books: List[SGPBooks] | List[RFQParlay], request: Request):
        books = [
            book.model_copy(
                update={"book_name": SPECIAL_MAPPING.get(book.book_name.lower(), book.book_name.lower())}
            )
            for book in books
        ] if books else []

        invalid_books = {
            book.book_name: None
            for book in books
            if book.book_name.lower() not in self.books
        }

        async with CurlAsyncSession(impersonate="safari15_5") as curl_session, aiohttp.ClientSession() as aiohttp_session:
            tasks = [self._call_book(
                book=book,
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


