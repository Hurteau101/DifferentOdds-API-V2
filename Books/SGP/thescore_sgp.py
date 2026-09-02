import asyncio
import copy
import re
from Books.Bases.sgp_base import SGPBookBase
from curl_cffi import AsyncSession as CurlAsyncSession

class ThescoreSGP(SGPBookBase):
    def __init__(self, sgp_data: dict, **kwargs):
        super().__init__(category="SGP", book_name="thescore", sgp_data=sgp_data, **kwargs)

    # Don't reuse session.
    async def run_book(self, session=None):
        link_data = self._custom_link_extract(self.links)

        if not link_data:
            return None

        async with CurlAsyncSession(impersonate="chrome") as session:
            data = await session.get("https://sportsbook.ca-default.thescore.bet/")
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

    async def _get_sgp_odds(self, session: CurlAsyncSession, auth_header: dict, market_selection:dict,
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
            session=session,
            url=self.book_data.url.get("sgp_url"),
            method="POST",
            headers={**self.book_data.headers, **auth_header},
            json=payload
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

    async def _load_bet_slip(self, session: CurlAsyncSession, link_data: list, auth_header: dict,
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
                session=session,
                url=self.book_data.url.get("draftbet_url"),
                method="POST",
                headers={**self.book_data.headers, **auth_header},
                json=payload
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

    async def _get_anonymous_token(self, session: CurlAsyncSession) -> str | None:
        headers = {
            "apollographql-client-version": "25.23.2",
            'X-APOLLO-OPERATION-NAME': 'Startup',
            "User-Agent": "theScore Bet/25.23.2 iPadOS/17.7.10 (iPhone; Retina, 750x1334, mobile)",
            "x-platform": "ios",
        }

        api_data = await self.api_caller(
            session=session,
            default_headers=False,
            url=self.book_data.url.get("anonymous_token_url"),
            method="GET",
            headers=headers,
        )

        if api_data and api_data.get("data"):
            anonymous_token = api_data.get("data", {}).get("startup", {}).get("anonymousToken")
            return f"Bearer {anonymous_token}"

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

            if odds_denominator and odds_numerator and selection_id:
                link_data.append({
                    "odds_numerator": int(odds_numerator.group(1)),
                    "odds_denominator": int(odds_denominator.group(1)),
                    "selection_id": selection_id.group(1),
                })

        return link_data if link_data else None


if __name__ == "__main__":
    async def main():
        async with CurlAsyncSession(impersonate="safari15_5") as session:
            sgp_data = {'book_name': 'thescore', 'links': [
                "https://sportsbook.thescore.bet/sport/baseball/organization/united-states/competition/mlb/event/9295c531-1a1c-4796-86b9-02cf4ca697ae/section/player_props?market_selection_id[0]=MarketSelection:c8ba616c-0957-40b6-baf8-f4b3b4777c5a&odds_numerator[0]=11&odds_denominator[0]=5",
                "https://sportsbook.thescore.bet/sport/baseball/organization/united-states/competition/mlb/event/9295c531-1a1c-4796-86b9-02cf4ca697ae/section/player_props?market_selection_id[0]=MarketSelection:78c6afee-419a-4e99-9b7f-a2a0a86c7277&odds_numerator[0]=11&odds_denominator[0]=5"
            ]}

            book = ThescoreSGP(sgp_data=sgp_data)
            data = await book.run_book(session=session)
            print(data)

    asyncio.run(main())
