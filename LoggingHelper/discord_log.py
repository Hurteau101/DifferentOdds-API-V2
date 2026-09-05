import os
from zoneinfo import ZoneInfo
from discordwebhook import Discord
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")

if not WEBHOOK_URL:
    raise ValueError("DISCORD_LOG_WEBHOOK_URL not set in environment variables.")


def send_discord_message(book_name: str, error_type: str, error_message: str, count: int):
    tag_id = os.getenv("DISCORD_LOG_TAG_ID")

    now = datetime.now(tz=ZoneInfo("America/Denver"))

    embed_fields = [
        {"name": "Book Name", "value": book_name},
        {"name": "Error Type", "value": error_type},
        {"name": "Error Message", "value": error_message},
        {"name": "Count", "value": f"Occurrences: {count}"}
    ]

    embed = {
        "title": f"{book_name}",
        "color": 0xE74C3,
        "fields": embed_fields,
        "footer": {"text": "DifferentOdds Logs"},
        "timestamp": now.isoformat(),
    }

    content = f"<@{tag_id}>" if tag_id else None

    discord = Discord(url=WEBHOOK_URL)
    discord.post(
        content=content,
        username=f"{book_name} — {error_type}",
        embeds=[embed],
    )
