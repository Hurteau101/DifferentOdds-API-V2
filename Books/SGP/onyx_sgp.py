import asyncio
import os
from dotenv import load_dotenv
from Books.Bases.sgp_book_base import SGPBookBase
from Redis.redis_manager import RedisAsyncManager
from curl_cffi import AsyncSession as CurlAsyncSession

class OnyxSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, sgp_data: dict, mapped_ids_redis_instance, **kwargs):
        super().__init__(category="SGP", book_name="onyx odds", sgp_data=sgp_data,
                         mapped_ids_redis_instance=mapped_ids_redis_instance, **kwargs)

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session):
        auth_token = await self.load_auth_token(key_name="onyx_auth")

        if not auth_token:
            return None

        mapped_ids = await self.load_mapped_ids(key_name="onyx_ids")

        if not mapped_ids:
            return None

        payload = {
            "betSelections": {
                mapped_ids[data["selection_id"]]["semantic_id"]: {
                    "marketDetails": {
                        "name": mapped_ids[data["selection_id"]]["name"],
                        "marketName": mapped_ids[data["selection_id"]]["market_name"],
                        "game": {
                            "fixtureId": mapped_ids[data["selection_id"]]["fixture_id"]
                        }
                    }
                }
                for data in self.link_data
                if data is not None
                   and (bet_id := data.get("selection_id")) is not None
                   and bet_id in mapped_ids
            }
        }

        api_data = await self.api_caller(
            use_proxy=True,
            url=self.book_data.url.get("main_url"),
            method=self.book_data.method,
            headers={
                "Authorization": f"Bearer {auth_token}"
            },
            json=payload
        )

        if not api_data:
            return None

        return OnyxSGP.return_odds(american_odds=api_data.get("price"), decimal_odds=None) if api_data.get("price") else None


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="chrome") as session:
            sgp_data = {
                "book_name": "onyxodds",
                "links": [
                    "https://app.onyxodds.com/game/19432-24860-2026-04-19?selection=0301a05a-6e06-4851-9c25-da1a80f03d32",
                    "https://app.onyxodds.com/game/19432-24860-2026-04-19?selection=47f989d6-b9f2-4fb4-b465-ebc18dbf0849",
                ],
            }

            redis_mapped = RedisAsyncManager(database=2)
            redis_instance = RedisAsyncManager(database=5)
            book = OnyxSGP(mapped_ids_redis_instance=redis_mapped, auth_redis_instance=redis_instance, sgp_data=sgp_data)
            data = await book.run_book(session=session)
            if data:
                print(data)

    asyncio.run(main())

