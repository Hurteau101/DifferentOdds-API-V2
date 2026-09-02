import os
import urllib
from urllib.parse import urlencode
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from curl_cffi import AsyncSession as CurlAsyncSession
import json

class FliffAuth(AuthBase):
    def __init__(self):
        super().__init__(book_name="fliff", category="sgp")
        self.basic_auth = os.getenv("COMMON_FLIFF_BASIC_AUTH_TOKEN")
        if not self.basic_auth:
            raise ValueError("FLIFF_BASIC_AUTH_TOKEN must be set in environment variables.")

    async def _get_location_token(self, session: CurlAsyncSession):
        location_auth = os.getenv("FLIFF_LOCATION_AUTH")
        user_id = os.getenv("FLIFF_USER_ID")

        if not user_id:
            raise ValueError("FLIFF_USER_ID must be set in environment variables.")

        payload = {
            "anonymous": False,
            "id": "69e84817d18734bf784fa1a2",
            "installId": "d2e08ed9-5d2f-4859-ab43-d2e04fce7e1b",
            "userId": user_id,
            "deviceId": "48e0c8468226f089",
            "metadata": {
                "fullName": " ",
                "userId": int(user_id),
                "meta_hash": "FVTFaT0x4N216Wl9BR0VHMV8xNzgyNDQ2MjM1NjQ4XzMz",
                "referrerUsername": "000-ODDSJAM",
                "app_x_version": "5.12.4.286",
                "referrerId": 822467,
                "device_x_id": "android.48e0c8468226f089"
            },
            "sessionId": "1782446180",
            "latitude": 47.444368,
            "longitude": -100.459284,
            "accuracy": 1000,
            "speed": 0,
            "verticalAccuracy": 0,
            "speedAccuracy": 1.5,
            "updatedAtMsDiff": 14967,
            "locationMs": 468217,
            "foreground": False,
            "stopped": True,
            "replayed": False,
            "deviceType": "Android",
            "deviceMake": "Genymobile",
            "sdkVersion": "3.21.3",
            "deviceModel": "Galaxy S9",
            "deviceOS": "13",
            "country": "US",
            "timeZoneOffset": 0,
            "source": "FOREGROUND_LOCATION",
            "xPlatformType": "ReactNative",
            "xPlatformSDKVersion": "3.20.3",
            "mocked": False,
            "nearbyGeofences": True,
            "nearbyGeofencesLimit": 10,
            "locationAuthorization": "GRANTED_FOREGROUND",
            "locationAccuracyAuthorization": "FULL",
            "trackingOptions": {
                "desiredStoppedUpdateInterval": 3600,
                "fastestStoppedUpdateInterval": 1200,
                "desiredMovingUpdateInterval": 1200,
                "fastestMovingUpdateInterval": 360,
                "desiredSyncInterval": 140,
                "desiredAccuracy": "medium",
                "stopDuration": 140,
                "stopDistance": 70,
                "replay": "stops",
                "sync": "all",
                "useStoppedGeofence": False,
                "stoppedGeofenceRadius": 0,
                "useMovingGeofence": False,
                "movingGeofenceRadius": 0,
                "syncGeofences": True,
                "syncGeofencesLimit": 10,
                "foregroundServiceEnabled": False,
                "beacons": False
            },
            "usingRemoteTrackingOptions": False,
            "locationServicesProvider": "GOOGLE",
            "verified": True,
            "integrityException": "-16: Standard Integrity API error (-16): The provided cloud project number is invalid.\nUse the cloud project number which can be found in Project info in your Google Cloud Console for the cloud project where Play Integrity API is enabled.\n (https://developer.android.com/google/play/integrity/reference/com/google/android/play/core/integrity/model/StandardIntegrityErrorCode.html#CLOUD_PROJECT_NUMBER_IS_INVALID).",
            "encrypted": False,
            "reason": "manual",
            "appId": "com.fliff.fapp",
            "appName": "Fliff",
            "appVersion": "5.12.4",
            "appBuild": 272
        }

        response = await self.api_caller(
            url="https://api-verified.radar.io/v1/track",
            headers={
                'Authorization': location_auth,
                'X-Radar-Config': 'true',
                'X-Radar-Device-Make': 'Genymobile',
                'X-Radar-Device-Model': 'Galaxy S9',
                'X-Radar-Device-OS': '13',
                'X-Radar-Device-Type': 'Android',
                'X-Radar-SDK-Version': '3.21.3',
                'X-Radar-Mobile-Origin': 'com.fliff.fapp',
                'X-Radar-X-Platform-SDK-Type': 'ReactNative',
                'X-Radar-X-Platform-SDK-Version': '3.20.3',
                'Connection': 'Keep-Alive'
            },
            method="POST",
            json=payload,
            session=session
        )

        if not response or not response.get("token"):
            return None

        return response.get("token")

    async def _reload_auth_on_expired_refresh(self, session: CurlAsyncSession):
        phone_number = os.getenv("FLIFF_PHONE_NUMBER")
        code = os.getenv("FLIFF_CODE")

        if not all([phone_number, code]):
            raise ValueError("FLIFF_BASIC_AUTH_TOKEN, FLIFF_PHONE_NUMBER, and FLIFF_CODE must be set in environment variables.")

        login_data = {
            "login_data": {
                "login_token": f"phone:+{phone_number}",
                "password": code,
                "meta_device_os": "web",
                "meta_app_version": "5.0.34",
                "meta_app_build": 285,
                "meta_install_token": "eGGpUCqUIu",
                "meta_device_id": "41e71aca97c561d67611edc1da8f47b3",
                "meta_product_code": 10,
                "meta_af_uid": "no_appsflyer_uid_for_web"
            },
            "__object_class_name": "Fliff_Login_Request"
        }

        payload = {
            "grant_type": "password",
            "username": "fliff_v2_auth",
            "password": json.dumps(login_data),
            "device_x_id": "web.41e71aca97c561d67611edc1da8f47b3",
            "product_code": 10,
            "af_uid": "no_appsflyer_uid_for_web"
        }

        encoded_data = urllib.parse.urlencode(payload)

        response = await self.api_caller(
            session=session,
            url=self.book_data.url.get("auth_url"),
            method=self.book_data.method,
            headers={
                'Authorization': f'Basic {self.basic_auth}',
                'x-dd-request-code': 'account_login',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            default_headers=False,
            data=encoded_data
        )

        if not all([response, response.get("access_token"), response.get("refresh_token")]):
            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.AUTH,
                error_message="Could not get access token or refresh token"
            )

        return {
            "access_token": response["access_token"],
            "refresh_token": response["refresh_token"],
        }

    async def _get_auth(self, session: CurlAsyncSession, refresh_token: str):
        response = await self.api_caller(
            session=session,
            url="https://app.getfliff.com/api/v1/oauth2/token/",
            method="POST",
            headers={
                'accept': 'application/json, text/plain, */*',
                'authorization': f'Basic {self.basic_auth}',
                'content-type': 'application/x-www-form-urlencoded',
            },
            default_headers=False,
            data=urlencode({
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'device_x_id': 'android.48e0c8468226f089'
            }),
        )

        return response.get("access_token")



    async def run_auth(self) -> bool:
        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            refresh_token = await self.redis_manager.get_data("fliff_refresh_token")
            location_token = await self._get_location_token(session)

            if not location_token:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not get location token"
                )
                return False

            if not refresh_token:
                print("No Refresh Token Found, Reloading Auth on Expired Refresh Token.")
                token_data = await self._reload_auth_on_expired_refresh(session=session)

                await self.store_data(
                    key_name="fliff_refresh_token",
                    data_to_store={
                        "refresh_token": token_data["refresh_token"],
                    },
                    expiration_time=2592000
                )

                await self.store_data(
                    key_name=self.auth_id_name,
                    data_to_store={
                        "access_token": token_data["access_token"],
                        "location_token": location_token,
                    },
                    expiration_time=200 # 3 Minutes
                )

                return True


            auth_token = await self._get_auth(session=session, refresh_token=refresh_token.get("refresh_token"))

            if not auth_token:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.AUTH,
                    error_message="Could not get auth token"
                )

                return False

            await self.store_data(
                key_name=self.auth_id_name,
                data_to_store={
                    "access_token": auth_token,
                    "refresh_token": refresh_token.get("refresh_token"),
                    "location_token": location_token,
                },
                expiration_time=200  # 3 Minutes
            )

            return True


if __name__ == "__main__":
    import asyncio
    fliff = FliffAuth()
    asyncio.run(fliff.run_auth())