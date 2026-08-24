from enum import Enum

from Authentication.ace_auth import AceAuth
from Authentication.buckeye2_auth import Buckeye2Auth
from Authentication.caesars_auth import CaesarAuth
from Authentication.chalkboard_auth import ChalkboardAuth
from Authentication.fliff_auth import FliffAuth
from Authentication.fourcx_auth import FourcxAuth
from Authentication.kibl_auth import KiblAuth
from Authentication.metallic_auth import MetallicAuth
from Authentication.onyx_auth import OnyxAuth


class RedisSelector(Enum):
    AUTH = 5
    MAPPER = 2

AUTH_JOBS = {
    "fliff": {
        "class": FliffAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 180,  # 3 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "fliff_auth_token",
    },
    "fourcx": {
        "class": FourcxAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 86400,  # 24 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "4cx_auth_token",
    },
    "caesars": {
        "class": CaesarAuth,
        "job_type": "auth",
        "is_active": False,
        "interval": 600,  # 10 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "caesars_waf_token",
    },
    "chalkboard": {
        "class": ChalkboardAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 3600,  # 1 hour
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "chalkboard_access_token",
    },
    "kibl": {
        "class": KiblAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 82800,  # 23 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "kibl_auth_token",
    },
    "onyx odds": {
        "class": OnyxAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 25200,  # 7 hours
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "onyx_auth",
    },
    "ace": {
        "class": AceAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "ace_cookies",
    },
    "metallic": {
        "class": MetallicAuth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "metallic_token",
    },
    "buckeye2": {
        "class": Buckeye2Auth,
        "job_type": "auth",
        "is_active": True,
        "interval": 900,  # 15 minutes
        "redis_db": RedisSelector.AUTH,
        "session_type": "aiohttp",
        "redis_key_checker_name": "buckeye_2_auth_token",
    }


}