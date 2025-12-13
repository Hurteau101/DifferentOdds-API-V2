import re
import copy
import aiohttp
from Settings.book_base import SportbookRequestType
from Settings.sgp_book_base import SGPBookBase
import asyncio

class Score_SGP(SGPBookBase):
    def __init__(self, links):
        super().__init__(SportbookRequestType.ASYNC,  log_directory="SGP Logs", log_name="thescore_sgp.log", sportsbook_name="thescore", links=links, skip_link_validation=True)

    @SGPBookBase.require_link_data
    async def run_book(self):
        link_data = self._custom_link_extract(self.link_data)
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

            draftbet_id = await self._get_draftbet_id(session, link_data, auth_header, length_of_links)

            if not draftbet_id:
                return None

            return await self._get_sgp_odds(session, auth_header, draftbet_id, length_of_links)

    async def _get_sgp_odds(self, session, auth_header, draftbet_id, length_of_links):
        payload = {
            "extensions": {
                "clientLibrary": {
                    "name": "apollo-ios",
                    "version": "1.21.0"
                },
                "persistedQuery": {
                    "sha256Hash": "c654d6f923b508a2fdd493b03ef9a1c7cc015eacedf03330c589373cdb87668b",
                    "version": 1
                }
            },
            "operationName": "BetslipSetDraftBetAmount",
            "variables": {
                "amount": "2000",
                "draftBetId": draftbet_id,
                "field": "BET",
                "isBetslipTeaserTabEnabled": True,
                "isMedia": False,
                "oddsFormat": "AMERICAN"
            }
        }

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("graph_url"),
            method="POST",
            headers={**self.book_data.headers, **auth_header},
            payload=payload
        )

        api_data = self.check_api_response(sportsbook="thescore", results=api_data)
        if not api_data.get("success"):
            return None

        bet_info = api_data.get("data", {}).get("betslipSetDraftBetAmount")
        errors = bet_info.get("errors")

        if len(errors) >= 1 or length_of_links != bet_info.get("numberOfSelections"):
            return None

        if not bet_info.get("minimizedBetslip", {}).get("betType") == "PARLAY_PLUS":
            return None

        sgp_odds = bet_info.get("minimizedBetslip", {}).get("odds", {}).get("formattedOdds")
        sgp_odds = {
            "decimal": None,
            "american": float(sgp_odds)
        }

        return sgp_odds if sgp_odds else None


    async def _get_draftbet_id(self, session, link_data, auth_header, length_of_links):
        """
        We need to extract the last draftbet ID after adding all selections one by one. Since theScore uses mutable state
        which adds each bet to the betslip, so the last draftbet ID corresponds to the full SGP bet.
        """
        base_payload = {
            "extensions": {
                "clientLibrary": {
                    "name": "apollo-ios",
                    "version": "1.21.0"
                },
                "persistedQuery": {
                    "sha256Hash": "e399dc3197027e387824de98527635b4b50e0a093bae1fff1763a867fd380834",
                    "version": 1
                }
            },
            "operationName": "BetslipAddMarketSelection",
            "variables": {
                "isBetslipTeaserTabEnabled": True,
                "isMedia": False,
                "oddsFormat": "AMERICAN"
            }
        }

        for index, link in enumerate(link_data, start=1):
            input_data = {
                "odds": {
                    "denominatorLong": str(link.get("odds_denominator")),
                    "numeratorLong": str(link.get("odds_numerator"))
                },
                "selectionId": link.get("selection_id")
            }


            payload = copy.deepcopy(base_payload)
            payload["variables"]["input"] = input_data

            api_data = await self.api_caller(
                session=session,
                url=self.book_data.url.get("graph_url"),
                method="POST",
                headers={**self.book_data.headers, **auth_header},
                payload=payload
            )

            api_data = self.check_api_response(sportsbook="thescore", results=api_data)

            if not api_data.get("success"):
                return None

            parlay_draftbets = (
                api_data
                .get("data", {})
                .get("betslipAddMarketSelection", {})
                .get("parlay", {})
                .get("draftBets", [])
            )

            draftbet_id = next(iter(parlay_draftbets), {}).get("id")

            if index == length_of_links:
                await asyncio.sleep(1) # Important to allow the betslip to be calculated as Parlay else it will be a straight.
                return draftbet_id

        return None

    async def _get_anonymous_token(self, session):
        additional_header = {"apollographql-client-version": "25.23.2", 'X-APOLLO-OPERATION-NAME': 'Startup'}

        api_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get("anonymous_token_url"),
            method="GET",
            headers={**self.book_data.headers, **additional_header},
        )

        api_data = self.check_api_response(sportsbook="thescore", results=api_data)
        if api_data.get("success") and api_data.get("data"):
            anonymous_token = api_data.get("data", {}).get("startup", {}).get("anonymousToken")
            return f"Bearer {anonymous_token}"

        else:
            self.file_logger.log(
                sportsbook="thescore",
                message="Can't extract anonymous token automatically",
                level="ERROR",
            )

            return None


    def _custom_link_extract(self, link_list: list):
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
    import asyncio

    links = [
        # Nylander Over 2.5 SOG
        "https://sportsbook.thescore.bet/sport/hockey/organization/united-states/competition/nhl/event/f6027af5-c067-45b6-986d-5b948c300448/section/player_props?market_selection_id[0]=MarketSelection:ff50e4d0-fd12-4dc8-a472-18b25336fa98&odds_numerator[0]=9&odds_denominator[0]=4",
        # Leafs Moneyline
        "https://sportsbook.thescore.bet/sport/hockey/organization/united-states/competition/nhl/event/f6027af5-c067-45b6-986d-5b948c300448/section/lines?market_selection_id[0]=MarketSelection:ce6f754b-1c28-4256-a964-65c01c0e6a63&odds_numerator[0]=11&odds_denominator[0]=5",
    ]

    score_sgp = Score_SGP(links)
    odds = asyncio.run(score_sgp.run_book())
    print(odds)