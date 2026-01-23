from old.SGP.hardrock_helper import HardRockHelper
from old.Settings.book_base import SportbookRequestType
from old.Settings.sgp_book_base import SGPBookBase

class Hardrock_SGP(SGPBookBase):
    def __init__(self, links, **kwargs):
        super().__init__(SportbookRequestType.ASYNC, sportsbook_name="hardrock", links=links, log_directory="SGP Logs", log_name="hardrock_sgp.log", decode_url=True, **kwargs)

    @staticmethod
    def convert_decimal_to_american(decimal_odds):
        """Convert decimal odds to American odds."""
        if decimal_odds is None:
            return None
        if decimal_odds >= 2.0:
            return float(round((decimal_odds - 1) * 100))
        else:
            return float(round(-100 / (decimal_odds - 1)))


    @SGPBookBase.require_link_data
    async def run_book(self):
        hardrock_ids = [self.link_data[i]["bet_id"] for i in range(len(self.link_data))]

        hardrock_extractor = HardRockHelper(hardrock_ids)
        api_data = hardrock_extractor.runner()
        if not api_data:
            self._api_call_log(
                sportsbook="hardrock_sgp",
                error_details="Failed to retrieve data from Hardrock API."
            )

        betslip_data = api_data[0].get("Betslip", {}) if isinstance(api_data, list) else api_data.get("Betslip", {})

        return next(
            (
                {
                    "decimal": price,
                    "american": self.convert_decimal_to_american(price),
                    "fractional": None,
                }
                for betslip in betslip_data.get("sameGameParlays", {}).values()
                if (price := betslip.get("price"))
            ),
            None
        )


if __name__ == "__main__":
    import asyncio

    links = [
        "https://hrbs.onelink.me/vTTH?af_web_dp=https://app.hardrock.bet/?deeplink=betslip-7466562111844122878&deep_link_value=hardrock://betslip/7466562111844122878",
        "https://hrbs.onelink.me/vTTH?af_web_dp=https://app.hardrock.bet/?deeplink=betslip-5474481238290727174&deep_link_value=hardrock://betslip/5474481238290727174",
    ]

    hardrock_sgp = Hardrock_SGP(links)
    odds = asyncio.run(hardrock_sgp.run_book())
    print(odds)