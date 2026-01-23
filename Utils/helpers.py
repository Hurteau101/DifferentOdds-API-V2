from dataclasses import asdict
from functools import lru_cache
from dateutil import parser
import pytz
from unidecode import unidecode

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