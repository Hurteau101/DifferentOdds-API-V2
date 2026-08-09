from Books.Bases.sgp_book_base import SGPBookBase
import asyncio
from Utils.socket_pooler import SocketHelper

# _pool = SocketPooler(url="wss://api.hardrocksportsbook.com/websocket", headers={
#     'Origin': 'https://api.hardrocksportsbook.com',
#     'Host': 'api.hardrocksportsbook.com'
# })

class HardrockSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(
            category="SGP",
            book_name="hardrock",
            sgp_data=sgp_data,
            **kwargs
        )



    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self, session=None):

        hardrock_ids = [item["bet_id"] for item in self.link_data]

        payload = self.create_payload(hardrock_ids)

        socket_helper = SocketHelper(
            url="wss://api.hardrocksportsbook.com/websocket",
            headers={
                'Origin': 'https://api.hardrocksportsbook.com',
                'Host': 'api.hardrocksportsbook.com'
            }
        )

        # data = await socket_helper.send(payload={
        #   "SportsbookLoginRequest": {
        #     "sessionToken": None
        #   }
        # })
        #
        # if data.get("Response", {}).get("status") != "ok":
        #     return None


        data = await socket_helper.send(payload)

        if not data:
            return None

        betslip_data = data.get("Betslip", {})

        odds = next(
            (
                {
                    "decimal": price,
                    "american": self.convert_decimal_to_american(price),
                }
                for betslip in betslip_data.get("sameGameParlays", {}).values()
                if (price := betslip.get("price"))
            ),
            None
        )

        return (
            HardrockSGP.return_odds(
                american_odds=odds.get("american"),
                decimal_odds=odds.get("decimal"),
            )
            if odds
            else None
        )



    def create_payload(self, hardrock_ids):

        return {
            "BetslipBuilderRequest": {
                "channel": "ARIZONA_ONLINE",
                "currency": "USD",
                "selections": [{"id": ids} for ids in hardrock_ids],
                "metadata": False
            }
        }

if __name__ == "__main__":

    sgp_data = {
        "book_name": "hardrock",
        "links": [
          "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/8181944312381178196",
          "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/1795042579159581007",
        ]
      }

    async def main():
        tasks = [HardrockSGP(sgp_data=sgp_data).run_book() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        for i, result in enumerate(results, 1):
            print(f"Result {i}: {result}")

    asyncio.run(main())