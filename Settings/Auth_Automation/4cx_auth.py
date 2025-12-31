import os

from dotenv import load_dotenv
import requests
import json
from Redis.redis_manager import RedisSync

load_dotenv()

def get_auth():
    redis = RedisSync(db=5)

    url = "https://api.4cx.io/user/login"

    payload = json.dumps({
        "username": os.getenv("4CX_USERNAME"),
        "password": os.getenv("4CX_PASSWORD")
    })

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/json',
        'x-user-socket-status': '',
        'x-price-socket-status': '',
        'Origin': 'https://4cx.io',
        'Connection': 'keep-alive',
        'Referer': 'https://4cx.io/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code == 200:
        auth_data = response.json()
        auth = auth_data.get("data", {}).get("user", {}).get("auth")
        print(auth)
        if not auth:
            return

        redis.set(
            key="4cx_auth_token",
            value=auth,
            ex=5270400   # 61 Days
        )


if __name__ == "__main__":
    get_auth()