import asyncio
from dotenv import load_dotenv
from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
import os
from curl_cffi import AsyncSession as CurlAsyncSession

class FliffSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, mapped_ids_redis_instance, **kwargs):
        super().__init__(category="SGP", book_name="fliff",
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)

    async def create_payload(self, sgp_token, location_token):
        mapped_ids = await self.load_mapped_ids(key_name="fliff_ids")

        if not mapped_ids:
            return None

        additional_data = self.sgp_data.get("event_data", [])
        merged_data = [mapped|additional for mapped, additional in zip(self.link_data, additional_data)]

        proposal_keys = []
        proposal_conflict_keys = {}


        for data in merged_data:
            event_id = data.get("event_id")
            market_name = data.get("market_name")
            selection_name = data.get("selection_name")
            proposal_key = mapped_ids.get(event_id, {}).get(market_name.lower(), {}).get(selection_name.lower())

            if not proposal_key:
                break

            proposal_keys.append(proposal_key)
            proposal_conflict_keys[proposal_key] = event_id

        if len(self.link_data) != len(proposal_keys) or len(self.link_data) != len(proposal_conflict_keys):
            return None

        return {
            "header": {
                "device_x_id": "android.48e0c8468226f089",
                "product_code": 10,
                "app_x_version": "5.12.4.286",
                "app_install_token": "U1ZOLx7mzZ",
                "auth_token": sgp_token,
                "conn_id": 2,
                "platform": "prod",
                "usa_state_code": "ND",
                "usa_state_code_source": "ipOrigin=2702|regionCode=ND|meta=successGetRegionCode|geocodeOrigin=2702|regionCode=ND|meta=successGetRegionCode",
                "xtag": "meta_2",
                "country_code": "US",
                "af_uid": "1776830401233-1374000387539042131",
                "authorization": "",
                "location_token": location_token,
            },
            "invocation": {
                "request": {
                    "__object_class_name": "FCM__Get_Parlay_Plus_Quote__Request",
                    "proposal_fkeys": proposal_keys,
                    "proposal_fkey_to_conflict_fkey": proposal_conflict_keys
                }
            },
            "x_invocations": None
        }

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        tokens = await self.load_auth_token(key_name="fliff_auth_token")
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
                "app_x_version": "5.12.4.286",
                "app_install_token": "U1ZOLx7mzZ",
                "auth_token": "fobj__sb_user_profile__1106610",
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
                    "https://sports.getfliff.com/markets?eventId=386070_c_p_203_prematch",
                    "https://sports.getfliff.com/markets?eventId=386070_c_p_203_prematch"
                ],
                'event_data': [
                    {'market_name': 'Moneyline', 'selection_name': 'mil brewers'},
                    {'market_name': 'Total Runs', 'selection_name': 'Under 7.5'}
                ]
            }

            redis_mapped = RedisAsyncManager(database=2)
            redis_instance = RedisAsyncManager(database=5)
            book = FliffSGP(mapped_ids_redis_instance=redis_mapped, sgp_data=sgp_data, auth_redis_instance=redis_instance)
            data = await book.run_book(session=session)
            print(data)


    asyncio.run(main())

