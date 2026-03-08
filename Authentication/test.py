import requests

proxy = "http://VhWs9J5KLW3g46N:A3u2WBR6o9mUDoD@204.252.80.137:45228"

proxies = {
    "http": proxy,
    "https": proxy
}

print(requests.get("https://api.ipify.org", proxies=proxies).text)