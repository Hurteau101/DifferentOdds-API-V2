import re
from dataclasses import asdict
from functools import lru_cache
from dateutil import parser
import pytz
from dotenv import load_dotenv
from unidecode import unidecode
import os
import importlib

load_dotenv()


def get_class_instance(class_name, class_path):
    module = importlib.import_module(class_path)
    class_name = getattr(module, class_name)
    class_instance = class_name()
    return class_instance


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

def decimal_to_american(decimal):
    """Convert decimal odds back to American odds."""
    if not decimal or decimal == 1.0:
        return None

    if decimal >= 2.0:
        return (decimal - 1) * 100
    else:
        return -100 / (decimal - 1)

def american_to_decimal(odds):
    """Convert American odds to decimal odds."""
    if odds is None:
        return None

    if odds > 0:
        return 1 + (odds / 100)
    else:
        return 1 + (100 / abs(odds))

def percentage_to_american_odds(probability):
    """
    Convert a decimal probability to rounded American odds.

    Args:
        probability (float): Decimal probability between 0 and 1.

    Returns:
        int: Rounded American odds (negative for probabilities > 0.5).

    Examples:
        >>> percentage_to_american_odds(0.25)
        300
    """
    if probability > 0.5:
        odds = -(100 * probability) / (1 - probability)
    else:
        odds = (100 * (1 - probability)) / probability

    return round(odds)

def convert_probability_to_american_odds(probability_str: str | float):
    """Converts a probability to American odds."""
    probability = float(probability_str)

    if not 0 <= probability <= 1:
        return None

    if probability == 0:
        return None
    if probability == 1:
        return None

    if probability > 0.5:
        american_odds = -(100 * probability) / (1 - probability)
    else:
        american_odds = (100 * (1 - probability)) / probability

    return round(american_odds)