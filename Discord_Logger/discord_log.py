import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from Redis.redis_manager import RedisSync
from dotenv import load_dotenv
from discordwebhook import Discord

class DiscordLog:
    def __init__(self, channel_name: str):
        load_dotenv()
        channel = self._channel_mapper(channel_name)
        if not channel:
            raise ValueError(f"Channel '{channel_name}' not found in mapper.")

        self.discord = Discord(url=channel)

    def _channel_mapper(self, channel_name: str):
        channel_mapper = {
            "auth": os.getenv("AUTH_CHANNEL_WEBHOOK_URL"),
        }

        channel_id = channel_mapper.get(channel_name)
        return channel_id if channel_id else ""

    def _role_mapper(self, role_name: str):
        role_mapper = {
            "caesars": os.getenv("CAESAR_LOGGING_ROLE_ID"),
        }

        role_id = role_mapper.get(role_name)
        return f"<@&{role_id}>" if role_id else ""


    def _logger(self, log_name: str, log_message: str, additional_fields=None):
        fields = [
            {
                "name": log_name,
                "value": log_message,
                "inline": False
            }
        ]

        if additional_fields:
            fields.append(additional_fields)

        embed = {
            "title": log_name,
            "fields": fields,
            "timestamp": datetime.now(tz=ZoneInfo("America/Denver")).isoformat()
        }

        return embed

    def send_logger(self, key_name:str, key_value: str, key_expiration, log_name: str, log_message: str, role_name: str = None, additional_fields=None):
        logs = self._logger(log_name, log_message, additional_fields)
        role_mention = self._role_mapper(role_name)
        redis_client = RedisSync(db=7)
        if redis_client.get(key_name):
            return

        redis_client.set(key_name, key_value, ex=key_expiration)

        self.discord.post(
            content=role_mention,
            embeds=[logs]
        )









