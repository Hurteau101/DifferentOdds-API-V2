import warnings
from dotenv import load_dotenv
from Books.SGP.draftkings_sgp import DraftkingsSGP
from Books.SGP.prophetx_sgp import ProphetxSGP
from Tests.SGP.setup import SGPSetUp

import pytest
load_dotenv()

# # This will automatically run the setup to get the SGP data for testing
# def automation():
#     def add_class(sgp_data: list):
#         """Add class and other details to the previously extracted SGP Data"""
#         return [
#             {
#                 **sgp,
#                 **sgp_mapper.get(sgp.get("book_name").lower())
#             }
#             for sgp in sgp_data
#             if sgp_mapper.get(sgp.get("book_name").lower()) is not None
#         ]
#
#     sgp_mapper = {
#         # "draftkings": {
#         #     "class": DraftkingsSGP,
#         #     "raise_on_no_odds": True,
#         # },
#         "prophetx": {
#             "class": ProphetxSGP,
#             "raise_on_no_odds": False,
#         }
#     }
#
#     default_league = "NBA"
#     market_names = ["Player Points", "Player Points + Rebounds"]
#
#
#     setup = SGPSetUp(markets=market_names, league=default_league)
#     grouped_filtered = setup.run_startup(used_stored_data=True, should_store_filtered=False, should_store_internal=True)
#
#     raw_sgp_data = [
#         setup.create_pairings(grouped_filtered, book)
#         for book in setup.return_valid_books()
#     ]
#
#     return add_class(raw_sgp_data)
#
# # Selection Options
# SELECTION = ["automation", "manual"]
#
# # Change this to switch between automation and manual selection
# TEST_SELECTION = SELECTION[1]
#
# # SGP_DATA = automation() if TEST_SELECTION == "automation" else MANUAL_SELECTION_SGP_DATA


# If using manual selection, please fill in the data.
# MANUAL_SELECTION_SGP_DATA = [
#     {
#         "book_name": "prophetx",
#         "class": ProphetxSGP,
#         "links": [
#             "https://www.prophetx.co/?action=addtobetslip&lineID=b559b66ebc54529cc9a51b30b78d1e55&partner_id=null&currency=cash",
#             "https://www.prophetx.co/?action=addtobetslip&lineID=b559b66ebc54529cc9a51b30b78d1e55&partner_id=null&currency=cash",
#         ]
#     }
# ]

SGP_DATA = [
    {
        "book_name": "prophetx",
        "class": ProphetxSGP,
        "links": [
            "https://www.prophetx.co/?action=addtobetslip&lineID=b559b66ebc54529cc9a51b30b78d1e55&partner_id=null&currency=cash",
            "https://www.prophetx.co/?action=addtobetslip&lineID=b559b66ebc54529cc9a51b30b78d1e55&partner_id=null&currency=cash",
        ]
    }
]



@pytest.mark.asyncio
@pytest.mark.parametrize("sgp_entry", SGP_DATA)
async def test_sgp(sgp_entry):
    # if not sgp_entry:
    #     pytest.skip(f"Skipping empty SGP entry.")
    #
    # if not all([sgp_entry.get("class"), sgp_entry.get("book_name"), sgp_entry.get("links")]):
    #     pytest.skip(f"Skipping incomplete SGP entry: {sgp_entry} - Ensure you have 'class', 'book_name', and 'links'.")

    book = sgp_entry.get("class")(sgp_data={
        "book_name": sgp_entry.get("book_name"),
        "links": sgp_entry.get("links"),
    })

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

