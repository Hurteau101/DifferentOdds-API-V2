import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class HardRockHelper:
    def __init__(self, ids):
        self.payload = self.create_payload(ids)

    def create_payload(self, hardrock_ids):
        payload = {
            "BetslipBuilderRequest": {
                "channel": "ARIZONA_ONLINE",
                "currency": "USD",
                "selections": [{"id": ids} for ids in hardrock_ids],
                "metadata": False
            }
        }
        return json.dumps(payload)

    def selenium_manger(self):
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
                const payload = {self.payload};

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

    def runner(self):
        data = self.selenium_manger()
        if data:
            return [json.loads(msg) for msg in data]