##### SEEMS LIKE YOU DON'T NEED TO LOGIN, AS YOU CAN JUST USE THE PLAYER DETAIL URL AND GET THE PLAYER TOKEN AND PASS THAT TO EVERYTHING ####

# import os
# import aiohttp
# from dotenv import load_dotenv
# from twocaptcha import TwoCaptcha
# from yarl import URL
# from APScheduler.base_scheduler import BaseScheduler
# from Redis.redis_manager import RedisAsyncManager
# from Utils.request_caller import SportbookRequestType
#
#
# class OneBVAuth(BaseScheduler):
#     URL = "https://everygame247.com/Integrations/Captcha"
#     load_dotenv()
#
#     def __init__(self):
#         super().__init__(request_type=SportbookRequestType.ASYNC)
#
#     async def run_scheduler(self, session: aiohttp.ClientSession, redis_instance: RedisAsyncManager):
#         username = os.getenv("1BV_USERNAME")
#         password = os.getenv("1BV_PASSWORD")
#         captcha_token = os.getenv("CAPTCHA_API_TOKEN")
#         user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
#
#         if not any([username, password, captcha_token]):
#             raise ValueError("Missing required environment variables: 1BV_USERNAME, 1BV_PASSWORD, CAPTCHA_API_TOKEN")
#
#         headers = {
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#             'Accept-Language': 'en-US,en;q=0.9',
#             'Accept-Encoding': 'gzip, deflate, br',
#             'Content-Type': 'application/x-www-form-urlencoded',
#             'Origin': 'https://everygame247.com',
#             'Referer': 'https://everygame247.com/',
#             'Connection': 'keep-alive',
#             'Upgrade-Insecure-Requests': '1',
#             'User-Agent': user_agent
#         }
#
#         await session.post(
#             url=OneBVAuth.URL,
#             data={
#                 "Username": username,
#                 "Password": password,
#             },
#             headers=headers,
#             allow_redirects=True
#         )
#
#         solver = TwoCaptcha(apiKey=captcha_token)
#         result = solver.turnstile(
#             sitekey='0x4AAAAAACGX1cBGMZzjhswX',
#             url='https://everygame247.com/Integrations/Captcha',
#             useragent=user_agent
#         )
#
#         token = result['code']
#
#         captcha_headers = headers.copy()
#         captcha_headers['Referer'] = 'https://everygame247.com/Integrations/Captcha'
#
#         await session.post(
#             'https://everygame247.com/Integrations/Captcha',
#             headers=captcha_headers,
#             data={'cf-turnstile-response': token},
#             allow_redirects=True
#         )
#
#         cookies = session.cookie_jar.filter_cookies(URL('https://everygame247.com'))
#         cookie_dict = {name: morsel.value for name, morsel in cookies.items()}
#
#         if not cookie_dict:
#             return
#
#         await redis_instance.store_data(
#             key_name="1bv_cookies",
#             data_to_store=cookie_dict,
#             key_expiration=1800 # 30 Minutes
#         )
#
#
#
# if __name__ == "__main__":
#     import asyncio
#     from Redis.redis_manager import RedisAsyncManager
#     import aiohttp
#
#
#     async def main():
#         redis_instance = RedisAsyncManager(database=5)
#         async with aiohttp.ClientSession() as session:
#             onebv = OneBVAuth()
#             await onebv.run_scheduler(session=session, redis_instance=redis_instance)
#         await redis_instance.close_for_shutdown()
#
#
#     asyncio.run(main())