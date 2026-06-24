from seleniumbase import SB
import time

REFRESH_INTERVAL = 5 * 60

with SB(uc=True, headless=False,
        user_data_dir="C:\\chrome-profile",
        chromium_arg="--remote-debugging-port=9222") as sb:
    sb.uc_open_with_reconnect("https://sportsbook.draftkings.com/", reconnect_time=4)
    print("Browser started up.")
    while True:
        time.sleep(REFRESH_INTERVAL)
        sb.refresh()