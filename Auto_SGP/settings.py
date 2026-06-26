from Books.SGP.betmgm_sgp import BetmgmSGP
from Books.SGP.betway_sgp import BetwaySGP
from Books.SGP.bovada_sgp import BovadaSGP
from Books.SGP.caesar_sgp import CaesarsSGP
from Books.SGP.draftkings_sgp import DraftkingsSGP
from Books.SGP.fanactics_sgp import FanaticsSGP
from Books.SGP.fanduel_sgp import FanduelSGP
from Books.SGP.fliff_sgp import FliffSGP
from Books.SGP.hardrock_sgp import HardrockSGP
from Books.SGP.kambi_sgp import KambiSGP
from Books.SGP.novig_sgp import NovigSGP
from Books.SGP.onyx_sgp import OnyxSGP
from Books.SGP.prophetx_sgp import ProphetxSGP
from Books.SGP.thescore_sgp import ThescoreSGP

BOOKS = {
    "betmgm": {
        "class": BetmgmSGP,
        "active": True,
        "mapped_name": "betmgm",
        "session": "aiohttp"
    },
    "draftkings": {
        "class": DraftkingsSGP,
        "active": True,
        "mapped_name": "draftkings",
        "session": "curl"
    },
    "fanatics": {
        "class": FanaticsSGP,
        "active": True,
        "mapped_name": "fanatics",
        "session": "aiohttp"
    },
    "fanduel": {
        "class": FanduelSGP,
        "active": True,
        "mapped_name": "fanduel",
        "session": "aiohttp"
    },
    "hard rock": {
        "class": HardrockSGP,
        "active": True,
        "mapped_name": "hardrock",
        "session": "aiohttp"
    },
    "kambi": {
        "class": KambiSGP,
        "active": True,
        "mapped_name": "kambi",
        "session": "aiohttp"
    },
    "novig": {
        "class": NovigSGP,
        "active": True,
        "mapped_name": "novig",
        "session": "aiohttp"
    },
    "onyx odds": {
        "class": OnyxSGP,
        "active": True,
        "mapped_name": "onyxodds",
        "session": "aiohttp"
    },
    "prophet x": {
        "class": ProphetxSGP,
        "active": True,
        "mapped_name": "prophetx",
        "session": "aiohttp"
    },
    "caesars": {
        "class": CaesarsSGP,
        "active": True,
        "mapped_name": "caesars",
        "session": "aiohttp"
    },
    "thescore": {
        "class": ThescoreSGP,
        "active": True,
        "mapped_name": "thescore",
        "session": "aiohttp"
    },
    "betway": {
        "class": BetwaySGP,
        "active": True,
        "mapped_name": "betway",
        "session": "curl"
    },
    "fliff": {
        "class": FliffSGP,
        "active": True,
        "mapped_name": "fliff",
        "session": "aiohttp"
    },
    "bovada": {
        "class": BovadaSGP,
        "active": True,
        "mapped_name": "bovada",
        "session": "aiohttp"
    }
}


