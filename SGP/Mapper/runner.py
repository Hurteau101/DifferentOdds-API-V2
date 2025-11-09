import asyncio

from SGP.Mapper.betmgm_mapper import BetMGM_Mapper
from SGP.Mapper.fanduel_mapper import Fanduel_Mapper
from SGP.Mapper.onyx_mapper import Onyx_Mapper


class Runner:
    books = {
        "betmgm": BetMGM_Mapper,
        "fanduel": Fanduel_Mapper,
        "onyx": Onyx_Mapper
    }

    async def run_mappers(self):
        tasks = [book().run_book() for book in Runner.books.values()]
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    runner = Runner()
    asyncio.run(runner.run_mappers())