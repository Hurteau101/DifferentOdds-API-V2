import asyncio
from Bases.mapper_base import MapperBase
from Books.Bases.sgp_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
import os
from curl_cffi import AsyncSession as CurlAsyncSession

class FliffSGP(SGPBookBase):
    def __init__(self, **kwargs):
        super().__init__(category="SGP", book_name="fliff", **kwargs)


    def _rebuild_additional_data(self, additional_data: list) -> list | None:
        """Rebuilds the additional data"""
        modified_data = []

        if not self.link_data:
            return None

        event_id = self.link_data[0].get("event_id")

        for data in additional_data:
            if data.get("prop_key"):
                modified_data.append({"event_key": event_id, "prop_key": data.get("prop_key")})
            else:
                prop_key = MapperBase.build_prop_key(side=data.get("side"), line=data.get("line"), player=data.get("player"), stat=data.get("market_name"))
                modified_data.append({"event_key": event_id, "prop_key": f"{prop_key}".lower()})


        return modified_data


    async def create_payload(self, sgp_token, location_token):
        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)

        if not mapped_ids:
            return None


        additional_data = self._rebuild_additional_data(additional_data=self.sgp_data.get("event_data", []))

        if not additional_data:
            return None


        proposal_keys = []
        proposal_conflict_keys = {}


        for data in additional_data:
            event_key = data.get("event_key")
            prop_key = data.get("prop_key")

            found = mapped_ids.get(event_key, {}).get(prop_key)
            if not found:
                return None

            key = found.get("id")
            proposal_keys.append(key)
            proposal_conflict_keys[key] = self.link_data[0].get("event_id")


        return {
            "header": {
                "product_code": 10,
                "device_x_id": "web.41e71aca97c561d67611edc1da8f47b3",
                "app_x_version": "5.0.34.285",
                "app_install_token": "eGGpUCqUIu",
                "auth_token": sgp_token,
                "conn_id": 34,
                "platform": "prod",
                "usa_state_code": "FL",
                "usa_state_code_source": "ipOrigin=2702|regionCode=FL|meta=successGetRegionCode|geocodeOrigin=2702|regionCode=FL|meta=successGetRegionCode",
                "xtag": "",
                "country_code": "US",
                "af_uid": "no_appsflyer_uid_for_web",
                "location_token": location_token,
            },
            "invocation": {
                "request": {
                    "__object_class_name": "FCM__Get_Parlay_Plus_Quote__Request",
                    "proposal_fkeys": proposal_keys,
                    "proposal_fkey_to_conflict_fkey": proposal_conflict_keys
                }
            },
            "x_invocations": None,
        }

    @SGPBookBase.ensure_link_data
    async def run_book(self, session):
        tokens = await self.auth_redis_manager.get_data(key_name=self.auth_id_name)

        if not tokens:
            return None

        access_token = tokens.get("access_token")
        location_token = tokens.get("location_token")

        sgp_token = os.getenv("FLIFF_SGP_TOKEN")

        if not access_token or not location_token or not sgp_token:
            return None

        payload = await self.create_payload(sgp_token=sgp_token, location_token=location_token)

        if not payload:
            return None

        api_data = await self.api_caller(
            session=session,
            params={
                "device_x_id":"android.48e0c8468226f089",
                "product_code": "10",
                "app_x_version": "5.12.4.286",
                "app_install_token": "U1ZOLx7mzZ",
                "auth_token": sgp_token,
                "conn_id": "2",
                "platform": "prod",
                "usa_state_code": "ipOrigin%3D2702%7CregionCode%3DND%7Cmeta%3DsuccessGetRegionCode%7CgeocodeOrigin%3D2702%7CregionCode%3DND%7Cmeta%3DsuccessGetRegionCode",
                "xtag": "meta_2",
                "country_code": "US",
                "af_uid": "1776830401233-1374000387539042131",
                "authorization": "",
                "location_token": location_token,
            },
            url=self.book_data.url.get("sgp_url"),
            method=self.book_data.method,
            headers={
                "device_x_id": "android.48e0c8468226f089",
                "product_code": "10",
                "app_install_token": "U1ZOLx7mzZ",
                "auth_token": sgp_token,
                "conn_id": "2",
                "platform": "prod",
                "usa_state_code": "ND",
                "usa_state_code_source": "ipOrigin=2702|regionCode=ND|meta=successGetRegionCode|geocodeOrigin=2702|regionCode=ND|meta=successGetRegionCode",
                "xtag": "meta_2",
                "country_code": "US",
                "af_uid": "1776830401233-1374000387539042131",
                "authorization": f"Bearer {access_token}",
                "location_token": location_token,
            },
            json=payload
        )

        if not api_data:
            return None

        odds_group = api_data.get("result", {}).get("response", {}).get("quotes", {})

        odds = next((
            odd_details.get("coeff")
            for odd_details in odds_group.values()
            if not odd_details.get("error_message") and odd_details.get("error_code") == 0
        ), None)

        if not odds:
            return None

        return FliffSGP.return_odds(
            american_odds=odds,
            decimal_odds=None
        )

if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                'book_name': 'fliff',
                'links': [
                    "https://sports.getfliff.com/markets?eventId=410962_c_p_203_prematch",
                    "https://sports.getfliff.com/markets?eventId=410962_c_p_203_prematch"
                ],
                "event_data": [
                    {
                        "market_name": "Total Runs",
                        "date": "2026-09-02T20:10:00Z",
                        "event_name": "Boston Red Sox vs Seattle Mariners",
                        "line": "8.5",
                        "player": "",
                        "side": "Under",
                        "prop_key": "8.5_total_runs_under",
                        "event_key": "boston_red_sox_vs_seattle_mariners_2026-09-02t20:10:00z"
                    },
                    {
                        "market_name": "Moneyline",
                        "date": "2026-09-02T20:10:00Z",
                        "event_name": "Boston Red Sox vs Seattle Mariners",
                        "line": "",
                        "player": "",
                        "side": "Seattle Mariners",
                        "prop_key": "moneyline_seattle_mariners",
                        "event_key": "boston_red_sox_vs_seattle_mariners_2026-09-02t20:10:00z"
                    }
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            redis_instance = RedisAsyncManager(database=5)
            book = FliffSGP(mapped_ids_redis_instance=redis_mapped, sgp_data=sgp_data, auth_redis_instance=redis_instance)
            data = await book.run_book(session=session)
            print(data)


    asyncio.run(main())

