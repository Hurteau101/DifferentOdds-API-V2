import asyncio
from dotenv import load_dotenv
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession

class OnyxSGP(SGPBookBase):
    load_dotenv()
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="onyx odds", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self, session):
        auth_token = await self.auth_redis_manager.get_data(key_name=self.auth_id_name)

        if not auth_token:
            return None

        mapped_ids = await self.mapper_redis_manager.get_data(key_name=self.mapper_id_name)

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
            json=payload,
            proxy_abort_text=["Error fetching parlay odds"]
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
                    "https://app.onyxodds.com/game/40644-20895-2026-09-01-16?selection=6d4229b0-82fb-43f6-9b8a-f4fc1dec2408",
                    "https://app.onyxodds.com/game/40644-20895-2026-09-01-16?selection=d1dde1ef-0b87-480c-aa8e-1015633787c5"
                ],
            }

            book = OnyxSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())

