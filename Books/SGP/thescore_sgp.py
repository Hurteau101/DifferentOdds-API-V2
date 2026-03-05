import asyncio
import copy
import re
import aiohttp
from Books.Bases.sgp_book_base import SGPBookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType

## If it stops fetching the SGP Odds - Look into proxying.

class ThescoreSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(request_type=SportbookRequestType.ASYNC, category="SGP", book_name="thescore", sgp_data=sgp_data, **kwargs)

    @SGPBookBase.retry_book(is_disabled=True)
    async def run_book(self):
        link_data = self._custom_link_extract(self.links)

        if not link_data:
            return None

        cookie_jar = aiohttp.CookieJar(unsafe=True)

        async with aiohttp.ClientSession(cookie_jar=cookie_jar) as session:
            await session.get("https://sportsbook.ca-default.thescore.bet/")

            token = await self._get_anonymous_token(session)

            if not token:
                return None

            auth_header = {
                "x-anonymous-authorization": token,
            }

            length_of_links = len(link_data)

            market_selection = await self._load_bet_slip(session, link_data, auth_header, length_of_links)

            if not market_selection:
                return None

            return await self._get_sgp_odds(session, auth_header, market_selection, length_of_links)


    async def _get_sgp_odds(self, session: aiohttp.ClientSession, auth_header: dict, market_selection:dict,
                            length_of_links: int) -> dict | None:
        payload = {
            "operationName": "BetslipAddMarketSelection",
            "variables": {
                "isSubscription": False,
                "input": {
                    "selectionId": market_selection.get("selection_id"),
                    "odds": {
                        "denominatorLong": market_selection.get("denominator"),
                        "numeratorLong": market_selection.get("numerator")
                    },
                    "selectionOrigin": None
                },
                "oddsFormat": "AMERICAN",
                "includeOddsTrend": True
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "11b043d75b61c332daff19bff740fb035a524d6d0fe9d12debc729c667633b61"
                }
            }
        }

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers={**self.book_data.headers, **auth_header},
            payload=payload
        )


        if not api_data:
            return None

        betslip = api_data.get("data", {}).get("betslipAddMarketSelection", {})

        if length_of_links != int(betslip.get("numberOfSelections")):
            return None

        odds = next((
            odds.get("totalOdds", {}).get("formattedOdds")
            for odds in betslip.get("parlay", {}).get("draftBets")
            if odds.get("isParlayPlusEligible", False)
        ), None)

        return ThescoreSGP.return_odds(american_odds=odds, decimal_odds=None) if odds else None

    async def _load_bet_slip(self, session:  aiohttp.ClientSession, link_data: list, auth_header: dict,
                             length_of_links: int) -> dict | None:
        """
        Add each bet to the betslip, since theScore uses mutable state. On the last bet, store the denominator,
        numerator & selection_id - As this will be used later on to extract the SGP odds.
        """

        base_payload = {
            "operationName": "BetslipAddMarketSelection",
            "variables": {
                "isSubscription": False,
                "input": {
                    "selectionOrigin": None,
                },
                "oddsFormat": "AMERICAN",
                "includeOddsTrend": True
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "11b043d75b61c332daff19bff740fb035a524d6d0fe9d12debc729c667633b61"
                }
            }
        }

        for index, link in enumerate(link_data, start=1):
            denominator = str(link.get("odds_denominator"))
            numerator = str(link.get("odds_numerator"))
            selection_id = link.get("selection_id")

            input_data = {
                "odds": {
                    "denominatorLong": denominator,
                    "numeratorLong": numerator,
                },
                "selectionId": selection_id,
            }

            payload = copy.deepcopy(base_payload)
            payload["variables"]["input"] = input_data

            api_data = await self.api_caller(
                book_name=self.book_data.name,
                session=session,
                url=self.book_data.url.get("draftbet_url"),
                method="POST",
                headers={**self.book_data.headers, **auth_header},
                payload=payload
            )

            if not api_data:
                return None

            await asyncio.sleep(1)

            if index == length_of_links:
                return {
                    "numerator": numerator,
                    "denominator": denominator,
                    "selection_id": selection_id,
                }

        return None

    async def _get_anonymous_token(self, session: aiohttp.ClientSession) -> str | None:
        headers = {
            "apollographql-client-version": "25.23.2",
            'X-APOLLO-OPERATION-NAME': 'Startup',
            "User-Agent": "theScore Bet/25.23.2 iPadOS/17.7.10 (iPhone; Retina, 750x1334, mobile)",
            "x-platform": "ios",
        }

        api_data = await self.api_caller(
            book_name=self.book_data.name,
            session=session,
            url=self.book_data.url.get("anonymous_token_url"),
            method="GET",
            headers=headers,
        )

        if api_data and api_data.get("data"):
            anonymous_token = api_data.get("data", {}).get("startup", {}).get("anonymousToken")
            return f"Bearer {anonymous_token}"

        else:
            create_sentry_message(
                tag_key=self.book_data.name,
                tag_value="auth_failure",
                message="Couldn't extract anonymous token",
                level="error"
            )
            return None


    def _custom_link_extract(self, link_list: list) -> list | None:
        """
        Extracts the denominator, numerator, and selection ID from sportsbook links.
        :param link_list: List of sportsbook links.
        :return: Extracted link data.
        """
        link_data = []

        if not link_list:
            return None

        for link in link_list:
            odds_denominator = re.search(r"odds_denominator\[0\]=(\d+)", link)
            odds_numerator = re.search(r"odds_numerator\[0\]=(\d+)", link)
            selection_id = re.search(r"market_selection_id\[0\]=([^&]+)", link)

            if odds_denominator and odds_denominator and selection_id:
                link_data.append({
                    "odds_numerator": int(odds_numerator.group(1)),
                    "odds_denominator": int(odds_denominator.group(1)),
                    "selection_id": selection_id.group(1),
                })

        return link_data if link_data else None


if __name__ == "__main__":
    sgp_data = {'book_name': 'thescore', 'links': ['https://sportsbook.thescore.bet/sport/basketball/organization/united-states/competition/nba/event/a0e973a2-833c-4ac8-9922-44e255916e27/section/player_props?market_selection_id[0]=MarketSelection:62fffb0a-1200-416e-bfd2-63e04c35e3e0&odds_numerator[0]=13&odds_denominator[0]=8', "https://sportsbook.thescore.bet/sport/basketball/organization/united-states/competition/nba/event/a0e973a2-833c-4ac8-9922-44e255916e27/section/player_props?market_selection_id[0]=MarketSelection:de13e23a-e0a2-4957-a961-113fa71fbd9b&odds_numerator[0]=43&odds_denominator[0]=23"]}

    thescore = ThescoreSGP(sgp_data=sgp_data)

    data = asyncio.run(thescore.run_book())
    print(data)