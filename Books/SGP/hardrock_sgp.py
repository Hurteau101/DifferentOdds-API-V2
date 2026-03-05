import asyncio
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class HardrockSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="hardrock", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.ensure_link_data
    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self):
        hardrock_ids = [self.link_data[i]["bet_id"] for i in range(len(self.link_data))]


        payload = self.create_payload(hardrock_ids)
        websocket_data = [json.loads(msg) for msg in self.selenium_manger(payload)]

        if not websocket_data:
            return None

        betslip_data = websocket_data[0].get("Betslip", {}) if isinstance(websocket_data, list) else websocket_data.get("Betslip", {})

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

        return HardrockSGP.return_odds(
            american_odds=odds.get("american"),
            decimal_odds=odds.get("decimal"),
        ) if odds else None

    def create_payload(self, hardrock_ids: list) -> str:
        payload = {
            "BetslipBuilderRequest": {
                "channel": "ARIZONA_ONLINE",
                "currency": "USD",
                "selections": [{"id": ids} for ids in hardrock_ids],
                "metadata": False
            }
        }
        return json.dumps(payload)

    def selenium_manger(self, payload) -> dict | None:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        driver = webdriver.Chrome(options=chrome_options)

        try:
            driver.get("about:blank")
            return driver.execute_async_script(f"""
                const callback = arguments[arguments.length - 1];
                const payload = {payload};

                const ws = new WebSocket("wss://api.hardrocksportsbook.com/websocket");
                let messages = [];

                ws.onopen = () => {{
                    ws.send(JSON.stringify(payload));
                }};

                ws.onmessage = (event) => {{
                    messages.push(event.data);
                    // Close immediately after receiving first message (optional)
                    ws.close();
                }};

                ws.onerror = () => {{
                    callback(null);
                }};

                ws.onclose = () => {{
                    callback(messages);
                }};
            """)
        except Exception as e:
            print("Error:", e)
            return None
        finally:
            driver.quit()


if __name__ == "__main__":
    sgp_data = {'book_name': 'hardrock', 'links': ['https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/6503125950346166615', 'https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/3088975220334264573']}
    hardrock = HardrockSGP(sgp_data=sgp_data)
    data = asyncio.run(hardrock.run_book())