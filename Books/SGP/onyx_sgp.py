import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType


class OnyxSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="onxy", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    async def run_book(self):
        if not self.auth_token:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="auth_failure",
                message="No auth found in Redis",
                level="error"
            )
            return None

        async with aiohttp.ClientSession() as session:
            mapped_ids = await self.load_mapped_ids(key_name="onyx_ids")

            if not mapped_ids:
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="mapping_failure",
                    message="No mapped IDs were found.",
                    level="error"
                )
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
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("main_url"),
                method=self.book_data.method,
                headers={
                    "Authorization": f"Bearer {self.auth_token}"
                },
                payload=payload
            )

            if not api_data:
                return None

            return OnyxSGP.return_odds(american_odds=api_data.get("price"), decimal_odds=None) if api_data.get("price") else None