import os

import httpx
from dotenv import load_dotenv

from Redis.redis_manager import RedisManager

load_dotenv()

async def generate_fanduel_picks_auth_token():
    redis = RedisManager(db=5)

    url = "https://api.fanduel.com/sessions"
    headers = {
        'X-Installation-id': '4F447867-D1A7-458E-8566-733351B5BB58',
        'Authorization': 'Basic ODc2YmQzOTE3ZWE3NjYwMjZhNjg5YzY2MTE5OGQxMmU6',
        'Origin': 'https://account.picks.fanduel.com',
        'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_7_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AppInfo (appDomain/picks; version/3.1.0; platform/ios)',
        'Referer': 'https://account.picks.fanduel.com/',
        'x-px-context': '_px3=99705c3762b3d26c2f7e4516c14c73b857d17593e997f68a14635d27a78c5103:3ThPM+kI8SNJ0Tcl6TLwv64UqGl9vfZAb0DpdSnx0tLUtOc1ge6wpgSE7SEtRun/u1tLods2UuMnfZhZmqkkKQ==:1000:ml+mfrodK+i+NvDYjFoiQniMV4AeS19X8pjfRuMg0wRsv0P3DnlDz1hhfRTcXRqfSUL5oYb4QuhGOZ5Kb7MHufC0F2nyOdcqkfICIjmJm6BJR+HfGuvHfSNbfrdavrh/oO4qY36e2Pm+wOt4qlHCUFWneW/bIatzEz+kivxE9c9UtQ9yBIUVaJoA2bCnY9GiDbweJONTWpqfk9gAjK3ae8v6+meYAPFUt28JB6dPh3k=;pxcts=6e9a5a65-8e5c-11f0-bebf-b69a35fb55c1',
        'Content-Type': 'application/json'
    }

    payload = {
        "email": os.getenv("FANDUEL_PICK_EMAIL"),
        "password": os.getenv("FANDUEL_PICK_PASSWORD"),
        "product": os.getenv("FANDUEL_PICK_PRODUCT"),
    }

    # Make the POST request to generate a new auth token - Using httpx for HTTP/2 support
    with httpx.Client(http2=True) as client:  # HTTP/2 enabled
        response = client.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            data = response.json()

            auth_token = next((
                auth_data.get("id")
                for auth_data in data.get("sessions", [])
            ), None)

            if auth_token:
                await redis.store_auth_token("fanduel_picks_auth_token", auth_token,
                                            key_expiration=12 * 3600)  # Store for 12 hours
                await redis.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_fanduel_picks_auth_token())