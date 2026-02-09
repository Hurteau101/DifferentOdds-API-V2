import warnings
from dotenv import load_dotenv

from Books.SGP.hardrock_sgp import HardrockSGP
from Books.SGP.kambi_sgp import KambiSGP
from Books.SGP.novig_sgp import NovigSGP
from Books.SGP.caesar_sgp import CaesarsSGP
from Books.SGP.betmgm_sgp import BetmgmSGP
from Books.SGP.draftkings_sgp import DraftkingsSGP
from Books.SGP.fanactics_sgp import FanaticsSGP
from Books.SGP.fanduel_sgp import FanduelSGP
from Books.SGP.onyx_sgp import OnyxSGP
from Books.SGP.prophetx_sgp import ProphetxSGP

import pytest

from Books.SGP.thescore_sgp import ThescoreSGP

load_dotenv()

# Todo:
# Run Mapper if book requires
# Run Auth if required
# Automation


SGP_DATA = [
    {
        "book_name": "prophetx",
        "active": True,
        "class": ProphetxSGP,
        "links": [
            "https://www.prophetx.co/?action=addtobetslip&lineID=f36b7c41ad90d596216769fdb9ac843c&partner_id=null&currency=cash",
            "https://www.prophetx.co/?action=addtobetslip&lineID=9b5740fcf961753ebaa9de98d77cdfa6&partner_id=null&currency=cash"
        ]
    },
    {
        "book_name": "betmgm",
        "class": BetmgmSGP,
        "requires_map": True,
        "active": True,
        "mapped_key": "betmgm_ids",
        "links": [
            "https://sports.{state}.betmgm.com/en/sports/events/18737708?options=18737708-1445020626--230589720&type=Single",
            "https://sports.{state}.betmgm.com/en/sports/events/18737708?options=18737708-1444781353--231206053&type=Single",
        ]
    },
    {
        "book_name": "caesars",
        "class": CaesarsSGP,
        "active": True,
        "requires_map": True,
        "requires_auth": True,
        "auth_key": "caesars_waf_token",
        "mapped_key": "caesar_mapped_ids",
        "links": [
"https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=080590fa-6455-320e-9b99-34e3358acbb4",
"https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=7332860f-5d69-31ef-9e4b-2108c82c6cd4"
        ],
        # "lines": {
        #         "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=3a8369b5-291c-3044-9ba1-ab3e9cc60eae": 7.5,
        #         "https://sportsbook.caesars.com/{country}/{state}/bet/betslip?selectionIds=60827514-f73b-36e7-9c19-248ad6ed7ee2": 7.5,
        #     }
    },
    {
        "book_name": "draftkings",
        "active": True,
        "class": DraftkingsSGP,
        "links": [

        ]
    },
    {
        "book_name": "fanatics",
        "class": FanaticsSGP,
        "active": True,
        "links": [
            "fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223704393%22%2C%22marketId%22%3A%22485124305%22%2C%22selectionId%22%3A%221204894861%22%7D%5D%7D&deep_link_value=consume-betslip",
            "fanaticssportsbook://discover/?deep_link_sub1=%7B%22legs%22%3A%5B%7B%22eventId%22%3A%223704393%22%2C%22marketId%22%3A%22485124121%22%2C%22selectionId%22%3A%221204894462%22%7D%5D%7D&deep_link_value=consume-betslip",
        ]
    },
    {
        "book_name": "fanduel",
        "class": FanduelSGP,
        "requires_map": True,
        "active": True,
        "mapped_key": "fanduel_ids",
        "links": [
            "https://sportsbook.fanduel.com/addToBetslip?marketId=42.552736131&selectionId=237478",
            "https://sportsbook.fanduel.com/addToBetslip?marketId=42.552736109&selectionId=7700282",
        ]
    },
    {
        "book_name": "hardrock",
        "class": HardrockSGP,
        "active": True,
        "links": [
            "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/8667080164317593855",
            "https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/8075247147462426876",
        ]
    },
    {
        "book_name": "kambi",
        "class": KambiSGP,
        "active": True,
        "links": [
            "https://{state}.betrivers.com/?page=sportsbook#event/1024652943?coupon=single|4040284066|",
            "https://{state}.betrivers.com/?page=sportsbook#event/1024652943?coupon=single|4040272388|",
        ]
    },
    {
        "book_name": "novig",
        "class": NovigSGP,
        "active": True,
        "links": [
            "https://app.novig.us/events/83325318-8807-4788-a9af-f28334b88d51/oddsjam",
            "https://app.novig.us/events/fae04132-1d8c-4103-8f0f-3a00de99019e/oddsjam",
        ]
    },
    {
        "book_name": "onyx",
        "class": OnyxSGP,
        "active": False,
        "links": [
        ]
    },
    {
        "book_name": "thescore",
        "class": ThescoreSGP,
        "active": True,
        "links": [
            "https://sportsbook.thescore.bet/sport/basketball/organization/united-states/competition/nba/event/949401fb-29fc-436b-833a-682c177b1d50/section/lines?market_selection_id[0]=MarketSelection:7d990733-d23b-4a75-ae7b-b167339ef422&odds_numerator[0]=41&odds_denominator[0]=21",
            "https://sportsbook.thescore.bet/sport/basketball/organization/united-states/competition/nba/event/949401fb-29fc-436b-833a-682c177b1d50/section/lines?market_selection_id[0]=MarketSelection:d92d7940-87ad-4fb7-9047-d414cc6b822c&odds_numerator[0]=7&odds_denominator[0]=6",
        ]
    },
]

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sgp_entry",
    [
        book for book in SGP_DATA
        if book.get("active") is True
    ],
    ids=lambda item: (item.get("book_name") or "unknown"),
)
async def test_sgp(sgp_entry, redis_mapper, redis_auth):
    async def get_mapped_ids(mapped_key: str):
        return await redis_mapper.get_data(mapped_key)

    async def get_auth_token(auth_key: str):
        return await redis_auth.get_data(auth_key)

    if not sgp_entry.get("links"):
        pytest.skip()

    requires_map = sgp_entry.get("requires_map", False)
    requires_auth = sgp_entry.get("requires_auth", False)

    if requires_map:
        if not sgp_entry.get("mapped_key"):
            raise KeyError("Must have mapped_key if using requires_map")

    if requires_auth:
        if not sgp_entry.get("auth_key"):
            raise KeyError("Must have auth_key if using requires_auth")


    auth_token = await get_auth_token(sgp_entry.get("auth_key")) if requires_auth else None
    mapped_ids = await get_mapped_ids(sgp_entry.get("mapped_key")) if requires_map else None

    book = sgp_entry.get("class")(
        sgp_data=
        {
            "book_name": sgp_entry.get("book_name"),
            "links": sgp_entry.get("links"),
            "lines": sgp_entry.get("lines"),
        },
        mapped_ids=mapped_ids,
        auth_token=auth_token
    )

    odds = await book.run_book()

    assert odds is not None, (
        f"""
        Book Failed: {sgp_entry['book_name']}
        Reason: Returned None
        Passed In: {sgp_entry['links']}
        """
    )

    assert isinstance(odds, dict), (
        f"""
        Book Failed: {sgp_entry['book_name']}
        Reason: Expected dict, got {type(odds).__name__}
        Passed In: {sgp_entry['links']}
        """
    )

    if len(odds) == 0:
        if sgp_entry.get("raise_on_no_odds"):
            raise AssertionError(
                f"""
                Book Failed: {sgp_entry['book_name']}
                Reason: returned empty odds
                Passed In: {sgp_entry['links']}
                """
            )
        else:
            warnings.warn(
                f"""
                Book Warning: {sgp_entry['book_name']}
                Reason: returned empty odds
                Passed In: {sgp_entry['links']}
                """,
                UserWarning
            )

    print(f"""
        Book Passed: {sgp_entry['book_name']}
        Returned Odds: {odds}
        Passed In: {sgp_entry['links']}
    """)

