import warnings
from dotenv import load_dotenv
from Redis.redis_manager import RedisAsyncManager
from Books.SGP.betmgm_sgp import BetmgmSGP
from Books.SGP.draftkings_sgp import DraftkingsSGP
from Books.SGP.prophetx_sgp import ProphetxSGP

import pytest
load_dotenv()

# Todo:
# Run Mapper if book requires
# Run Auth if required
# Automation


SGP_DATA = [
    # {
    #     "book_name": "prophetx",
    #     "class": ProphetxSGP,
    #     "links": [
    #         "https://www.prophetx.co/?action=addtobetslip&lineID=f36b7c41ad90d596216769fdb9ac843c&partner_id=null&currency=cash",
    #         "https://www.prophetx.co/?action=addtobetslip&lineID=9b5740fcf961753ebaa9de98d77cdfa6&partner_id=null&currency=cash"
    #     ]
    # },
    {
        "book_name": "betmgm",
        "class": BetmgmSGP,
        "requires_map": True,
        "mapped_key": "betmgm_ids",
        "links": [
            "https://sports.{state}.betmgm.com/en/sports/events/18737708?options=18737708-1445020626--230589720&type=Single",
            "https://sports.{state}.betmgm.com/en/sports/events/18737708?options=18737708-1444781353--231206053&type=Single",
        ]
    }
]

@pytest.mark.asyncio
@pytest.mark.parametrize("sgp_entry", SGP_DATA)
async def test_sgp(sgp_entry):
    async def get_mapped_ids(mapped_key: str):
        redis_instance = RedisAsyncManager(database=2)
        return await redis_instance.get_data(mapped_key)


    if sgp_entry.get("requires_map", False):
        if not sgp_entry.get("mapped_key"):
            raise KeyError("Must have mapped_key if using requires_map")

    mapped_ids = await get_mapped_ids(sgp_entry.get("mapped_key"))

    book = sgp_entry.get("class")(
        sgp_data=
        {
            "book_name": sgp_entry.get("book_name"),
            "links": sgp_entry.get("links"),
        },
        mapped_ids=mapped_ids
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

