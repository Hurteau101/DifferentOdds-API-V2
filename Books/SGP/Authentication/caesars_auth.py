import os
from Books.Bases.auth_base import AuthBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Utils.request_caller import PredefinedProxy
from curl_cffi import AsyncSession as CurlAsyncSession


class CaesarAuth(AuthBase):
    def __init__(self):
        super().__init__(book_name="caesars", category="sgp", precalculated_additional_time=240)

    async def run_auth(self) -> bool:
        api_key = os.getenv("CAPSOLVER_API_KEY")

        if not api_key:
            raise ValueError("CAPSOLVER_API_KEY must be set in environment variables.")

        proxy_list = PredefinedProxy.PROXY_CHEAP_RESIDENTIAL_PROXIES.value
        url = "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb/v2/bets/details"
        challenge_js_url = "https://b470c5d1aeb4.edge.sdk.awswaf.com/b470c5d1aeb4/06faba802dee/challenge.js"

        async with CurlAsyncSession(impersonate=self.impersonate) as session:
            for proxy in proxy_list:
                task = {
                    "type": "AntiAwsWafTask",
                    "websiteURL": url,
                    "awsChallengeJS": challenge_js_url,
                    "proxy": f"http://{proxy}"
                }

                response = await self.api_caller(
                    session=session,
                    url="https://api.capsolver.com/createTask",
                    method="POST",
                    json={"clientKey": api_key, "task": task},
                )

                if not response or not response.get("taskId"):
                    insert_log(
                        book_name=self.book_data.title,
                        error_type=ErrorTypes.MISC,
                        error_message="Couldn't create task ID with Capsolver"
                    )

                    return False

                for _ in range(15):
                    response = await self.api_caller(
                        session=session,
                        url=f"https://api.capsolver.com/getTaskResult",
                        method="POST",
                        json={"clientKey": api_key, "taskId": response["taskId"]},
                    )

                    status = response.get("status")

                    if status == "ready":
                        token = response.get("solution", {}).get("cookie")
                        if not token:
                            break

                        await self.store_data(
                            key_name=self.auth_id_name,
                            data_to_store=token,
                            expiration_time=self.pre_calculated_redis_expiration
                        )

                        return True

                    if response.get("errorId") or status == "failed":
                        break

            insert_log(
                book_name=self.book_data.title,
                error_type=ErrorTypes.AUTH,
                error_message="All proxies failed and no captcha could be solved, could not extract auth"
            )

            return False



if __name__ == "__main__":
    import asyncio
    caesar = CaesarAuth()
    asyncio.run(caesar.run_auth())
