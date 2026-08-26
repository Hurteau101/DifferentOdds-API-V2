import re
from dataclasses import asdict
from functools import lru_cache
from dateutil import parser
import pytz
from dotenv import load_dotenv
from unidecode import unidecode
import os

load_dotenv()

def serialize_data(data) -> list[dict]:
    """Serialize data to JSON format."""
    return [asdict(player_data) for player_data in data]

def clean_structure(structure_data: any):
    """Recursively clean and normalize string fields in a dataclass or nested structures."""
    if isinstance(structure_data, str):
        return clean_and_normalize(structure_data)

    if isinstance(structure_data, list):
        return [clean_and_normalize(item) for item in structure_data]

    if isinstance(structure_data, dict):
        return {key: clean_and_normalize(value) for key, value in structure_data.items()}

    return structure_data


def clean_and_normalize(string_name: str):
    """Clean and normalize a string name by removing special characters,"""
    if not string_name:
        return string_name

    if string_name.endswith('…'):
        string_name = string_name[:-1]

    string_name = re.sub(r'^[\d-]+\s+', '', string_name).strip()

    return unidecode(string_name).strip()



def convert_to_utc(date_time_str) -> str | None:
    """Convert the date to UTC format"""
    if date_time_str is None:
        return None

    parsed_time = parser.parse(date_time_str)
    utc_time = parsed_time.astimezone(pytz.utc)

    return utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

@lru_cache(maxsize=1000)
def cache_time(date_time_str) -> str | None:
    """Convert the date to UTC format and cache the result"""
    return convert_to_utc(date_time_str)


def ordinal_formatter(market_name):
    """Format the string if it is an ordinal market, otherwise return the original string."""
    pattern = r'\b\d+(st|nd|rd|th)\b'
    result = re.sub(pattern, lambda m: m.group(0), market_name, flags=re.IGNORECASE)

    if re.search(pattern, market_name, flags=re.IGNORECASE):
        result_split = result.split()

        return f"{result_split[0]} {' '.join(word.capitalize() for word in result_split[1:])}"

    return ' '.join(word.capitalize() for word in market_name.split())

def is_production():
    """Check if the environment is production."""
    is_prod = os.getenv("IS_PRODUCTION")

    if not is_prod:
        raise RuntimeError("Environment not set")

    return bool(is_prod.lower() == "true")
