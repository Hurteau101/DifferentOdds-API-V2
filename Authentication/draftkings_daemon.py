from seleniumbase import SB
import time
import os

REFRESH_INTERVAL = 5 * 60
USER_DATA_DIR = "C:\\chrome-profile" if os.name == "nt" else "/home/administrator/chrome-profile"



with SB(uc=True, headless=False,
        user_data_dir=USER_DATA_DIR,
        chromium_arg="--remote-debugging-port=9222") as sb:
    sb.uc_open_with_reconnect("https://sportsbook.draftkings.com/", reconnect_time=4)
    print("Browser started up.")

    while True:
        time.sleep(REFRESH_INTERVAL)
        sb.refresh()