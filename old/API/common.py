from functools import lru_cache
from typing import Literal, Optional
from fastapi import Header, HTTPException
from pydantic import BaseModel
from old.Settings.sportsbook_config import SportsbookConfig

class FormatHeader(BaseModel):
    format: Literal["Base", "Game"] = "Game"

class Books(BaseModel):
    title: str
    book_key: str
    status: str

@lru_cache(maxsize=None)
def get_cached_books(book_type: str):
    return SportsbookConfig.get_book_info(book_type=book_type)


def validate_format_header(
    format: Optional[str] = Header(None, alias="X-Format", description="Select output format: Base or Game")
):
    format = (format or "Game").capitalize()

    if format not in ["Base", "Game"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be one of: Base or Game."
        )

    return FormatHeader(format=format)
