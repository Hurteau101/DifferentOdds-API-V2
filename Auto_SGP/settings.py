from Books.SGP.betmgm_sgp import BetmgmSGP
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

URLS = {
    "bettorodds_url": "https://api.eternity7.dev/api/dev_internal_feed"
}

BOOKS = {
    "betmgm": {
        "class": BetmgmSGP,
        "active": True,
        "mapped_name": "betmgm"
    },
    "draftkings": {
        "class": DraftkingsSGP,
        "active": True,
        "mapped_name": "draftkings"
    },
    "fanatics": {
        "class": FanaticsSGP,
        "active": True,
        "mapped_name": "fanatics"
    },
    "fanduel": {
        "class": FanduelSGP,
        "active": True,
        "mapped_name": "fanduel"
    },
    "hard rock": {
        "class": HardrockSGP,
        "active": False,
        "mapped_name": "hardrock"
    },
    "kambi": {
        "class": KambiSGP,
        "active": True,
        "mapped_name": "kambi"
    },
    "novig": {
        "class": NovigSGP,
        "active": True,
        "mapped_name": "novig"
    },
    "onyx odds": {
        "class": OnyxSGP,
        "active": False,
        "mapped_name": "onyxodds"
    },
    "prophet x": {
        "class": ProphetxSGP,
        "active": True,
        "mapped_name": "prophetx"
    },
    "caesars": {
        "class": CaesarsSGP,
        "active": True,
        "mapped_name": "caesars"
    },
    "thescore": {
        "class": ThescoreSGP,
        "active": True,
        "mapped_name": "thescore"
    }

}


