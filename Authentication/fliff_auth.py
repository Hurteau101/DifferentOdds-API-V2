import os
from urllib.parse import urlencode
from dotenv import load_dotenv
from Authentication.base_auth import BaseAuth
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession


class FliffAuth(BaseAuth):
    load_dotenv()

    def __init__(self):
        super().__init__(book_name="fliff", category="sgp")

    async def get_location_token(self, location_auth, session):
        payload = {
            "anonymous": False,
            "id": "69e84817d18734bf784fa1a2",
            "installId": "d2e08ed9-5d2f-4859-ab43-d2e04fce7e1b",
            "userId": "1106610",
            "deviceId": "48e0c8468226f089",
            "metadata": {
                "fullName": " ",
                "userId": 1106610,
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



    async def run_scheduler(self, session: CurlAsyncSession, redis_instance: RedisAsyncManager) -> bool:
        basic_auth = os.getenv("FLIFF_BASIC_AUTH_TOKEN")
        refresh_token = os.getenv("FLIFF_REFRESH_TOKEN")
        location_auth = os.getenv("FLIFF_LOCATION_AUTH")

        if not basic_auth or not refresh_token or not location_auth:
            raise ValueError("FLIFF_BASIC_AUTH_TOKEN and FLIFF_REFRESH_TOKEN must be set in environment variables.")

        location_token = await self.get_location_token(location_auth=location_auth, session=session)

        if not location_token:
            return False

        response = await self.api_caller(
            session=session,
            url="https://app.getfliff.com/api/v1/oauth2/token/",
            method="POST",
            headers={
                'accept': 'application/json, text/plain, */*',
                'authorization': f'Basic {basic_auth}',
                'content-type': 'application/x-www-form-urlencoded',
            },
            default_headers=False,
            data=urlencode({
                'grant_type': 'refresh_token',
                'refresh_token': os.getenv("FLIFF_REFRESH_TOKEN"),
                'device_x_id': 'android.48e0c8468226f089'
            }),

        ) or {}

        if response.get("access_token"):
            await redis_instance.store_data(
                key_name=self.auth_id_name,
                data_to_store={
                    "access_token": response["access_token"],
                    "location_token": location_token,
                },
                key_expiration=response.get("expires_in", 300)  # 5 Minutes
            )

            return True

        return False





if __name__ == "__main__":
    import asyncio
    from Redis.redis_manager import RedisAsyncManager

    redis_instance = RedisAsyncManager(database=5)
    fliff = FliffAuth()

    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            await fliff.run_scheduler(session, redis_instance)

    asyncio.run(main())