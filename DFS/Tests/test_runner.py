import asyncio
from DFS.betr import Betr
from DFS.boom import Boom
from DFS.dabble import Dabble
from DFS.drafters import Drafters
from DFS.draftkings_6 import DraftKingsPickSix
from DFS.ownerbox import Ownerbox
from DFS.parlayplay import Parlayplay
from DFS.parlaye import Parlaye
from DFS.prizepicks import Prizepicks
from DFS.sleeper import Sleeper
from DFS.splashsports import SplashSports
from DFS.underdog import Underdog

async def run_with_print(book):
    name = book.__class__.__name__
    print(f"Starting {name}")
    try:
        await book.run_book()
        print(f"Finished {name}.")
    except Exception as e:
        print(f"Error running {name}: {e}")

# Test to run all DFS Books -- This is a test to ensure that all books can be initialized and run without errors.
async def main():
    books = [
        Betr(),
        Boom(),
        Dabble(),
        Drafters(),
        DraftKingsPickSix(),
        Ownerbox(),
        Parlayplay(),
        Parlaye(),
        Prizepicks(),
        Sleeper(),
        SplashSports(),
        Underdog()
    ]

    await asyncio.gather(*(run_with_print(book) for book in books))


if __name__ == "__main__":
    asyncio.run(main())
    print("All DFS books have been run successfully.")