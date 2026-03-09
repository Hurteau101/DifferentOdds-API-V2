# import asyncio
# import aiohttp
# from Books.Bases.sgp_book_base import SGPBookBase
# from Utils.request_caller import SportbookRequestType
# import json
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
#
# class HardrockSGP(SGPBookBase):
#     def __init__(self, sgp_data: dict, **kwargs):
#         super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="hardrock", sgp_data=sgp_data, **kwargs)
#
#     @SGPBookBase.ensure_link_data
#     @SGPBookBase.retry_book(is_disabled=True)
#     async def run_book(self, session=None):
#         hardrock_ids = [self.link_data[i]["bet_id"] for i in range(len(self.link_data))]
#
#         payload = self.create_payload(hardrock_ids)
#         raw_messages = await asyncio.to_thread(self.selenium_manger, payload)
#
#         if not raw_messages:
#             return None
#
#         # websocket_data = [json.loads(msg) for msg in raw_messages]
#
#         websocket_data = []
#
#         for msg in raw_messages:
#             if not msg:
#                 continue
#
#             try:
#                 websocket_data.append(json.loads(msg))
#             except json.JSONDecodeError:
#                 continue
#
#         if not websocket_data:
#             return None
#
#         betslip_data = websocket_data[0].get("Betslip", {}) if isinstance(websocket_data, list) else websocket_data.get("Betslip", {})
#
#         odds = next(
#             (
#                 {
#                     "decimal": price,
#                     "american": self.convert_decimal_to_american(price),
#                 }
#                 for betslip in betslip_data.get("sameGameParlays", {}).values()
#                 if (price := betslip.get("price"))
#             ),
#             None
#         )
#
#         return HardrockSGP.return_odds(
#             american_odds=odds.get("american"),
#             decimal_odds=odds.get("decimal"),
#         ) if odds else None
#
#     # @SGPBookBase.ensure_link_data
#     # @SGPBookBase.retry_book(is_disabled=True)
#     # async def run_book(self, session=None):
#     #     hardrock_ids = [self.link_data[i]["bet_id"] for i in range(len(self.link_data))]
#     #
#     #
#     #     payload = self.create_payload(hardrock_ids)
#     #     websocket_data = [json.loads(msg) for msg in self.selenium_manger(payload)]
#     #
#     #     if not websocket_data:
#     #         return None
#     #
#     #     betslip_data = websocket_data[0].get("Betslip", {}) if isinstance(websocket_data, list) else websocket_data.get("Betslip", {})
#     #
#     #     odds = next(
#     #         (
#     #             {
#     #                 "decimal": price,
#     #                 "american": self.convert_decimal_to_american(price),
#     #             }
#     #             for betslip in betslip_data.get("sameGameParlays", {}).values()
#     #             if (price := betslip.get("price"))
#     #         ),
#     #         None
#     #     )
#     #
#     #     return HardrockSGP.return_odds(
#     #         american_odds=odds.get("american"),
#     #         decimal_odds=odds.get("decimal"),
#     #     ) if odds else None
#
#     def create_payload(self, hardrock_ids: list) -> str:
#         payload = {
#             "BetslipBuilderRequest": {
#                 "channel": "ARIZONA_ONLINE",
#                 "currency": "USD",
#                 "selections": [{"id": ids} for ids in hardrock_ids],
#                 "metadata": False
#             }
#         }
#         return json.dumps(payload)
#
#
#     def selenium_manger(self, payload, print_logs: bool = False) -> dict | None:
#         chrome_options = Options()
#         # chrome_options.add_argument("--headless=new")
#         # chrome_options.add_argument("--disable-gpu")
#         # chrome_options.add_argument("--no-sandbox")
#         # chrome_options.add_argument("--disable-dev-shm-usage")
#         # chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
#         chrome_options.add_argument("--headless=new")
#         chrome_options.add_argument("--disable-gpu")
#         chrome_options.add_argument("--no-sandbox")
#         chrome_options.add_argument("--disable-dev-shm-usage")
#         chrome_options.add_argument("--disable-extensions")
#         chrome_options.add_argument("--disable-infobars")
#         chrome_options.add_argument("--remote-debugging-port=9222")
#         chrome_options.add_argument("--window-size=1920,1080")
#         chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
#
#         driver = webdriver.Chrome(options=chrome_options)
#
#         driver.set_script_timeout(7)
#
#         driver.get("about:blank")
#         try:
#             driver.get("about:blank")
#             result = driver.execute_async_script(f"""
#             const callback = arguments[arguments.length - 1];
#             const payload = {payload};
#
#             const ws = new WebSocket("wss://api.hardrocksportsbook.com/websocket");
#
#             let messages = [];
#             let finished = false;
#
#             function finish(result) {{
#                 if (finished) return;
#                 finished = true;
#                 callback(result);
#             }}
#
#             ws.onopen = () => {{
#                 console.log("WebSocket opened");
#                 ws.send(JSON.stringify(payload));
#             }};
#
#             ws.onmessage = (event) => {{
#                 console.log("Received message:", event.data);
#                 messages.push(event.data);
#                 ws.close();
#             }};
#
#             ws.onerror = (event) => {{
#                 console.log("WebSocket error:", event);
#                 finish({{error: "WebSocket error"}});
#             }};
#
#             ws.onclose = () => {{
#                 console.log("WebSocket closed");
#                 finish(messages);
#             }};
#
#             setTimeout(() => {{
#                 console.log("Timeout reached");
#                 finish(messages);
#             }}, 5000);
#             """)
#
#
#             # result = driver.execute_async_script(f"""
#             #     const callback = arguments[arguments.length - 1];
#             #     const payload = {payload};
#             #
#             #     const ws = new WebSocket("wss://api.hardrocksportsbook.com/websocket");
#             #     let messages = [];
#             #
#             #     ws.onopen = () => {{
#             #         console.log("WebSocket opened");
#             #         ws.send(JSON.stringify(payload));
#             #     }};
#             #
#             #     ws.onmessage = (event) => {{
#             #         console.log("Received message:", event.data);
#             #         messages.push(event.data);
#             #         ws.close();
#             #     }};
#             #
#             #     ws.onerror = (event) => {{
#             #         console.log("WebSocket error:", event);
#             #         callback({{error: "WebSocket error"}});
#             #     }};
#             #
#             #     ws.onclose = (event) => {{
#             #         console.log("WebSocket closed:", event.code);
#             #         callback(messages);
#             #     }};
#             # """)
#
#             # if print_logs:
#             #     logs = driver.get_log("browser")
#             #     for log in logs:
#             #         print("Hardrock Log:", log["message"])
#             #
#             #     print("Total Results:", result)
#
#             if not result:
#                 logs = driver.get_log("browser")
#                 for log in logs:
#                     print("Hardrock Log:", log["message"])
#
#                 print("Total Results:", result)
#
#             return result
#
#         except Exception as e:
#             print(f"Error in selenium_manger: {e}")
#             import traceback
#             traceback.print_exc()
#             return None
#
#         finally:
#             driver.quit()
#
#
# if __name__ == "__main__":
#     sgp_data = {
#         "book_name": "hardrock",
#         "links": [
#             "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/1226838881559773437",
#             "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/8030162598496436481",
#         ],
#     }
#     hardrock = HardrockSGP(sgp_data=sgp_data)
#     data = asyncio.run(hardrock.run_book())
#     print(data)
#
#



import asyncio
import json
from playwright.async_api import async_playwright

from Books.Bases.sgp_book_base import SGPBookBase
from Utils.request_caller import SportbookRequestType


class HardrockBrowserPool:
    _instance = None
    _lock = None
    _loop = None

    def __init__(self, size: int = 4):
        self.size = size
        self.browser = None
        self.pages = asyncio.Queue()
        self.playwright = None
        self.started = False

    # @classmethod
    # async def get_instance(cls):
    #
    #     if cls._lock is None:
    #         cls._lock = asyncio.Lock()
    #
    #     async with cls._lock:
    #         if cls._instance is None:
    #             cls._instance = HardrockBrowserPool()
    #             await cls._instance.start()
    #
    #     return cls._instance

    @classmethod
    async def get_instance(cls):
        loop = asyncio.get_running_loop()

        if cls._loop != loop:
            cls._instance = None
            cls._lock = None
            cls._loop = loop

        if cls._lock is None:
            cls._lock = asyncio.Lock()

        async with cls._lock:
            if cls._instance is None:
                cls._instance = HardrockBrowserPool()
                await cls._instance.start()

        return cls._instance


    # @classmethod
    # def limit(cls):
    #     if cls.hardrock_limit is None:
    #         cls.hardrock_limit = asyncio.BoundedSemaphore(4)
    #     return cls.hardrock_limit

    async def start(self):
        if self.started:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)

        for _ in range(self.size):
            page = await self.browser.new_page()
            await page.goto("https://app.hardrock.bet")
            await self.pages.put(page)

        self.started = True

    async def acquire(self):
        return await self.pages.get()

    async def release(self, page):
        await self.pages.put(page)

    async def shutdown(self):
        try:
            if self.browser:
                await self.browser.close()
        finally:
            self.browser = None

        try:
            if self.playwright:
                await self.playwright.stop()
        finally:
            self.playwright = None
            self.started = False


class HardrockSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(
            request_type=SportbookRequestType.ASYNC,
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

        raw_messages = await self.websocket_manager(payload)

        if not raw_messages:
            return None

        websocket_data = []

        for msg in raw_messages:
            try:
                websocket_data.append(json.loads(msg))
            except:
                continue

        if not websocket_data:
            return None

        betslip_data = websocket_data[0].get("Betslip", {})

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


    async def websocket_manager(self, payload):

        pool = await HardrockBrowserPool.get_instance()
        page = await pool.acquire()

        messages = []

        def handle_ws(ws):

            def handle_frame(frame):
                try:
                    messages.append(frame)
                except:
                    pass

            ws.on("framereceived", handle_frame)

        try:

            page.on("websocket", handle_ws)

            await page.evaluate(
                """
                (payload) => {

                    const ws = new WebSocket("wss://api.hardrocksportsbook.com/websocket");

                    ws.onopen = () => {
                        ws.send(JSON.stringify(payload));
                    };

                    ws.onmessage = (event) => {
                        console.log(event.data);
                    };
                }
                """,
                payload
            )

            await asyncio.sleep(2)

        finally:
            page.remove_listener("websocket", handle_ws)
            await pool.release(page)

        return messages




if __name__ == "__main__":

    sgp_data = {
        "book_name": "hardrock",
        "links": [
            "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/1226838881559773437",
            "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/8030162598496436481",
        ],
    }

    async def main():
        hardrock = HardrockSGP(sgp_data=sgp_data)

        data = await hardrock.run_book()
        print(data)

        pool = await HardrockBrowserPool.get_instance()
        await pool.shutdown()

    asyncio.run(main())

