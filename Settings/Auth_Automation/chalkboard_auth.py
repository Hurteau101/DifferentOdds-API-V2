import json

import requests
import os
from dotenv import load_dotenv
from Redis.redis_manager import RedisSync
load_dotenv()

def generate_auth() -> tuple | None:
    token_url = os.getenv("CHALKBOARD_TOKEN_URL")
    api_key = os.getenv("CHALKBOARD_API_KEY")
    headers = {
        "x-android-package": "com.taild",
        "x-android-cert": os.getenv("CHALKBOARD_ANDROID_CERT"),
        "accept-language": "en-US",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-A065F Build/UP1A.231005.007)",
        "Content-Type": "application/json",
    }

    payload = {
        "grantType": os.getenv("CHALKBOARD_GRANT_TYPE"),
        "refreshToken": os.getenv("CHALKBOARD_REFRESH_TOKEN")
    }

    response = requests.post(
        url=f"{token_url}?key={api_key}",
        headers=headers,
        data=json.dumps(payload),
    )

    if response.status_code == 200:
        data = response.json()

        return data.get("access_token", ""), data.get("refresh_token", "")

    return None

async def generate_chalkboard_auth():
    redis_instance = RedisSync(db=5)
    redis_instance.get("chalkboard_refresh_token")
    access_token, refresh_token = generate_auth()

    if not access_token:
        return

    if refresh_token:
        redis_instance.set(
            key="chalkboard_refresh_token_backup",
            value=refresh_token,
        )

    if access_token:
        redis_instance.set(
            key="chalkboard_access_token",
            value=access_token,
            ex=3600
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_chalkboard_auth())
