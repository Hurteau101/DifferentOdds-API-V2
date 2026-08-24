import re
from typing import Union
from urllib.parse import urlparse, parse_qs, quote

class Link:
    def link_creator(self, payload: list) -> dict:
        """
        Create multi-leg betslip links for different sportsbooks.
        :param payload: The payload containing book names and their respective links.
        :return: Returns a dictionary with sportsbook names as keys and their combined betslip links as values.
        """
        mapper = {
            "fanduel": self._fanduel,
            "hardrock": self._hardrock,
            "draftkings": self._draftkings,
            "onyxodds": self._onyxodds,
            "betmgm": self._betmgm,
            "novig": self._novig,
            "thescore": self._thescore,
            "caesars": self._caesar
        }

        results = {}

        for book in payload:
            book_name = book.get("book_name")
            links = book.get("links", [])
            if book_name in mapper:
                url_results = mapper[book_name](links)
                if url_results:
                    results[book_name] = url_results

        return results



    def _common_query_extractor(self, links: list, query_name: str) -> Union[str | list]:
        """
        Common query extractor for links.
        :param links: List of links.
        :param query_name: Query name to extract.
        :return: Returns a list of extracted query values.
        """
        parts = []

        for index, link in enumerate(links):
            parsed = urlparse(link)
            query_string = parse_qs(parsed.query)

            outcomes = query_string.get(query_name, [None])[0]
            outcomes = quote(outcomes, safe="")

            if not outcomes:
                return ""

            parts.append(outcomes)

        return parts

    def _caesar(self, links: list) -> str:
        """
        Build caesar multi-leg betslip link.
        :param links: List of caesar links.
        :return: Returns the combined BetMGM caesar link.
        """
        base_url = "https://sportsbook.caesars.com/us/az/bet/betslip?selectionIds="

        parts = self._common_query_extractor(links, "selectionIds")
        if not parts:
            return ""

        return base_url + ",".join(parts)

    def _novig(self, links: list) -> dict:
        """
        Build Novig multi-leg betslip link.
        :param links: List of Novig links.
        :return: Returns the combined Novig betslip link for mobile and desktop.
        """
        web_base_url = "https://novig.com/events/"
        mobile_base_url = "https://novig.onelink.me/JHQQ/events/"

        bet_ids = ",".join(
            [
                link_match.group(0)
                for link in links
                if (link_match := re.search(r"(?<=events/)[^/]+", link))
            ]
        )

        if len(bet_ids.split(",")) != len(links):
            return {}

        return {
            "desktop": web_base_url + bet_ids,
            "mobile": mobile_base_url + bet_ids
        }

    def _betmgm(self, links: list) -> str:
        """
        Build BetMGM multi-leg betslip link.
        :param links: List of BetMGM links.
        :return: Returns the combined BetMGM betslip link.
        """

        parts = self._common_query_extractor(links, "options")
        if not parts:
            return ""

        base_url = f"https://sports.ks.betmgm.com/en/sports/?options="
        return base_url + ",".join(parts)


    def _onyxodds(self, links: list) -> str:
        """
        Build Onyxodds multi-leg betslip link.
        :param links: List of Onyxodds links.
        :return: Returns the combined Onyxodds betslip link.
        """

        base_url = re.match(r"[^?]+", links[0]).group(0)

        if not base_url:
            return ""

        parts = self._common_query_extractor(links, "selection")

        if not parts:
            return ""

        query = "&".join(f"selection={p}" for p in parts)

        return f"{base_url}?{query}"



    def _hardrock(self, links: list) -> str:
        """
        Build Hardrock multi-leg betslip link.
        :param links: List of Hardrock links.
        :return: Returns the combined Hardrock betslip link.
        """
        base = "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/"

        bet_ids = ",".join(
            [
                link_match.group(0)
                for link in links
                if (link_match := re.search(r"(?<=//betslip/).*", link))
            ]
        )

        if len(bet_ids.split(",")) != len(links):
            return ""

        return base + bet_ids

    def _draftkings(self, links: list) -> str:
        """
        Build Draftkings multi-leg betslip link.
        :param links: List of Draftking links.
        :return: Returns the combined Draftking betslip link.
        """
        base = "https://sportsbook.draftkings.com?outcomes="
        parts = self._common_query_extractor(links, "outcomes")
        if not parts:
            return ""

        return base + ",".join(parts)


    def _fanduel(self, links: list) -> str:
        """
        Build Fanduel multi-leg betslip link.
        :param links: List of Fanduel links.
        :return: Returns the combined Fanduel betslip link.
        """
        base = "https://sportsbook.fanduel.com/addToBetslip?"

        parts = []

        for index, link in enumerate(links):
            parsed = urlparse(link)
            query_string = parse_qs(parsed.query)

            market = query_string.get("marketId", [None])[0]
            selection = query_string.get("selectionId", [None])[0]

            if not market or not selection:
                return ""

            parts.append(f"marketId[{index}]={market}")
            parts.append(f"selectionId[{index}]={selection}")

        return base + "&".join(parts)

    def _thescore(self, links: list) -> str:
        """
        Build thescore multi-leg betslip link.
        :param links: List of thescore links.
        :return: Returns the combined Fanduel thescore link.
        """

        parts = []

        for index, link in enumerate(links):
            parsed = urlparse(link)
            query = parse_qs(parsed.query)

            market = query.get("market_selection_id[0]", [None])[0]
            num = query.get("odds_numerator[0]", [None])[0]
            den = query.get("odds_denominator[0]", [None])[0]

            if not market or not num or not den:
                return ""

            parts.append(f"market_selection_id[{index}]={market}")
            parts.append(f"odds_numerator[{index}]={num}")
            parts.append(f"odds_denominator[{index}]={den}")

        first = urlparse(links[0])
        base = f"{first.scheme}://{first.netloc}{first.path}?"

        return base + "&".join(parts)


