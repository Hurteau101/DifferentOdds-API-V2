import os
from typing import Literal, cast
import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.celery import CeleryIntegration

load_dotenv()

IS_PRODUCTION = os.getenv("ENVIRONMENT") == "PRODUCTION"

def init_sentry():
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENVIRONMENT"),
        send_default_pii=True,
        traces_sample_rate=1.0 if IS_PRODUCTION else 0.0,
        shutdown_timeout=2 if IS_PRODUCTION else 0,
        integrations=[
            CeleryIntegration(),
        ],
    )

SentryLevel = Literal["fatal", "critical", "error", "warning", "info", "debug"]

def create_sentry_message(tag_key: str, tag_value: str, message: str, level: SentryLevel = "error"):
    """Create and send a Sentry message with a specific tag, level and message"""
    levels = ["fatal", "critical", "error", "warning", "info", "debug"]
    if level not in levels:
        level = "error"

    # Used for type hinting.
    sentry_level = cast(SentryLevel, level)

    if IS_PRODUCTION:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag(tag_key, tag_value)
            sentry_sdk.capture_message(message, level=sentry_level)

