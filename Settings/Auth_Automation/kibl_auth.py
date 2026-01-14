import os
import requests
from dotenv import load_dotenv
from Redis.redis_manager import RedisSync

load_dotenv()

URL = "https://cognito-idp.us-west-2.amazonaws.com/"
HEADERS = {
    'accept': 'application/json',
    'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    'Content-Type': 'application/x-amz-json-1.1'
}

def _extract_auth_refresh(response: requests.Response):
    if response.status_code == 200:
        data = response.json()
        auth_token = data.get("AuthenticationResult", {}).get("AccessToken")
        refresh_token = data.get("AuthenticationResult", {}).get("RefreshToken")
        auth_expiry = data.get("AuthenticationResult", {}).get("ExpiresIn")
        return auth_token, refresh_token, auth_expiry
    return None, None, None

def get_auth_from_refresh(redis_instance: RedisSync, refresh_token: str):
    payload = {
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": os.getenv("KIBL_APP_CLIENT"),
        "AuthParameters": {
            "REFRESH_TOKEN": refresh_token
        }
    }

    response = requests.post(URL, headers=HEADERS, json=payload)
    return _extract_auth_refresh(response)


def get_auth_no_refresh(redis_instance: RedisSync):
    payload = {
        "AuthParameters": {
            "USERNAME": os.getenv("KIBL_USERNAME"),
            "PASSWORD": os.getenv("KIBL_PASSWORD")
        },
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": os.getenv("KIBL_APP_CLIENT")
    }

    response = requests.post(URL, headers=HEADERS, json=payload)
    return _extract_auth_refresh(response)


if __name__ == "__main__":
    redis = RedisSync(db=5)
    check_refresh = redis.get("kibl_refresh_token").decode("utf-8") if redis.get("kibl_refresh_token") else None
    if not check_refresh:
        auth, refresh, expiry = get_auth_no_refresh(redis_instance=redis)
    else:
        auth, refresh, expiry = get_auth_from_refresh(redis_instance=redis, refresh_token=check_refresh)

    if auth and expiry:
        redis.set(
            key="kibl_auth_token",
            value=auth,
            ex=expiry
        )

    if refresh:
        redis.set(
            key="kibl_refresh_token",
            value=refresh,
            ex=2678400   # 31 Days
        )