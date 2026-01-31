import requests
import uuid
import re

# =====================
# CONFIG
# =====================
EMAIL = "worldgamingchamp123@gmail.com"
PASSWORD = "Global101!"

PROXY = "http://worldgamingchamp123:rNVt9ZDSo4@151.247.186.34:50100"

LOGIN_PAGE = "https://app.onyxodds.com/login"
LOGIN_API = "https://app.onyxodds.com/login"

# =====================
# SESSION SETUP
# =====================
session = requests.Session()
session.proxies.update({
    "http": PROXY,
    "https": PROXY
})

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "text/x-component",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "text/plain;charset=UTF-8",
    "Origin": "https://app.onyxodds.com",
    "Referer": "https://app.onyxodds.com/login",
}

# =====================
# STEP 1: GET LOGIN PAGE (SETS COOKIES + CSRF)
# =====================
r = session.get(LOGIN_PAGE, headers=headers)
r.raise_for_status()

# =====================
# STEP 2: EXTRACT CSRF TOKEN
# =====================
csrf_token = None

for cookie in session.cookies:
    if cookie.name == "__Host-authjs.csrf-token":
        csrf_token = cookie.value.split("|")[0]
        break

if not csrf_token:
    raise RuntimeError("CSRF token not found")

# =====================
# STEP 3: BUILD PAYLOAD
# =====================
payload = [
    {
        "email": EMAIL,
        "password": PASSWORD,
        "emailCode": "",
        "smsCode": "",
        "deviceId": str(uuid.uuid4())
    },
    None,
    csrf_token
]

# =====================
# STEP 4: SEND LOGIN REQUEST
# =====================
response = session.post(
    LOGIN_API,
    headers=headers,
    json=payload
)

data = session.get("https://app.onyxodds.com/api/auth/session")
print("The Data", data.json())
for c in session.cookies:
    print(f"{c.name} = {c.value}")

print(session.cookies)
print("STATUS:", response.status_code)
print("RESPONSE:", response.text)

# =====================
# DEBUG COOKIES AFTER LOGIN
# =====================
print("\nCookies:")
for c in session.cookies:
    print(f"{c.name} = {c.value}")
