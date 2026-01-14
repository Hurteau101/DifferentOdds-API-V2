import asyncio
import aiohttp
from orjson import orjson
from sportsbook.bet105 import Bet105
from Redis.redis_manager import RedisSync

class KiblMapper(Bet105):
    async def get_sportsbooks(self, session: aiohttp.ClientSession) -> list:
        """Get the list of supported sportsbooks"""
        raw_books = await self.api_caller(
                    session=session,
                    url=self.book_data.url.get("sportsbooks"),
                    headers=self.book_data.headers,
                    method=self.book_data.method
                )

        return [
            {
                "book_name": book.get("name"),
                "feed_source_id": book.get("feed_source_id"),
            }

            for book in raw_books.get("result", [])
            if raw_books.get("success") and raw_books.get("result")
        ]

    async def get_leagues(self, session: aiohttp.ClientSession) -> dict:
        """Get the list of supported leagues"""
        raw_leagues = await self.api_caller(
            session=session,
            url=self.book_data.url.get("leagues"),
            headers=self.book_data.headers,
            method=self.book_data.method
        )

        excluded_leagues = ["WTA", 'MMA', "UFC", "BOX", "ATP"] # REMOVE AFTER INVERSE CALCULATIONS IS FIXED

        return {
            league.get("league_id"): {
                "league_name": league.get("name"),
                "league_abbr": league.get("abrv"),
            }

            for league in raw_leagues.get("result", [])
            if league and raw_leagues.get("success") and raw_leagues.get("result")
               and league.get("abrv") not in excluded_leagues and "tennis" not in league.get("name").lower() # REMOVE AFTER INVERSE CALCULATIONS IS FIXED
        }

    async def get_mapping_types(self, session: aiohttp.ClientSession, url_key: str, mapping_key_name: str,
                                mapping_value_name: str) -> dict:
        """
        Generic method to get mapping types from the API
        @param session: aiohttp ClientSession
        @param url_key: Key to access the URL from book_data
        @param mapping_key_name: The key name to map
        @param mapping_value_name: The value name to map
        """
        if not all([url_key, mapping_key_name, mapping_value_name]):
            raise ValueError("All parameters must be provided and non-empty.")

        raw_data = await self.api_caller(
            session=session,
            url=self.book_data.url.get(url_key),
            headers=self.book_data.headers,
            method=self.book_data.method
        )

        return {
            data.get(mapping_key_name): data.get(mapping_value_name)
            for data in raw_data.get("result", [])
            if data and raw_data.get("success") and raw_data.get("result")
        }


    async def run_mapper(self):
        auth_token = self.get_auth()

        if not auth_token:
            return

        async with aiohttp.ClientSession() as session:
            self.book_data.headers["Authorization"] = auth_token
            sportsbooks = await self.get_sportsbooks(session)
            leagues = await self.get_leagues(session)

            #### MAY NOT NEED SINCE FIXTURES HAS PARTICIPANT INFO NOW ####
            # participants_raw = [
            #     self.api_caller(
            #         session=session,
            #         url=self.book_data.url.get("participants"),
            #         parms={"league_id": ",".join(map(str, league_id_chunk))},
            #         headers=self.book_data.headers,
            #         method=self.book_data.method
            #     )
            #     for league_id_chunk in self.chunk(list(leagues.keys()), 15)
            # ]
            #
            # participant_results = await asyncio.gather(*participants_raw)
            #
            # if not participant_results:
            #     return
            #
            # modified_league = {}
            #
            # for result in participant_results:
            #     if not result:
            #         continue
            #     for participant in result.get("result"):
            #         league_id = participant.get("league_id")
            #         fetched_league = leagues.get(league_id)
            #         if fetched_league:
            #             if league_id in modified_league:
            #                 modified_league.get(league_id).get("participants").update({
            #                     participant.get("participant_id"): {
            #                         "participant_name": participant.get("name"),
            #                         "participant_abbr": participant.get("abrv"),
            #                     }
            #                 })
            #
            #                 continue
            #
            #             modified_league.update({
            #                 league_id: {
            #                     **fetched_league,
            #                     "participants": {
            #                         participant.get("participant_id"): {
            #                             "participant_name": participant.get("name"),
            #                             "participant_abbr": participant.get("abrv"),
            #                         }
            #                     }
            #                 }
            #
            #             })
            #
            #         league_id = participant.get("league_id")
            #         fetched_league = leagues.get(league_id) if league_id else None
            #         if fetched_league:
            #             participants = fetched_league.setdefault("participants", {})
            #             participants[participant.get("participant_id")] = {
            #                 "participant_name": participant.get("name"),
            #                 "participant_abbr": participant.get("abrv"),
            #             }


            market_mapper_dict = {
                "segments": ["segment_id", "name"], # Full Game, First Quarter, etc..
                "sides": ["side_id", "name"], # Home, Away, Over, Under, Yes etc..
                # "market_genre": ["market_genre_id", "name"], # Game Market, Player Props, Team Props, etc..
                "market_status": ["market_status_id", "name"], # Open, Closed, Suspended, etc..
                "market_types": ["market_type_id", "name"], # Spread, Moneyline, SOG, etc..
                "fixture_types": ["fixture_type_id", "name"], # Future, Player Prop, Team
            }

            tasks = [
                self.get_mapping_types(
                    session=session,
                    url_key=url_key,
                    mapping_key_name=mapping_info[0],
                    mapping_value_name=mapping_info[1]
                )

                for url_key, mapping_info in market_mapper_dict.items()
            ]

            results = await asyncio.gather(*tasks)

            mapped_results = {
                url_key: result
                for (url_key, _), result in zip(market_mapper_dict.items(), results)
            }

            mapped_data = {
                "sportsbooks": sportsbooks,
                "leagues": leagues,
                **mapped_results
            }

            if mapped_data:
                redis = RedisSync(db=2)
                redis.set(
                    key="kibl_mapper_data",
                    value=orjson.dumps(mapped_data, option=orjson.OPT_NON_STR_KEYS),
                    ex=90000  # 25 hours expiration
                )


if __name__ == "__main__":
    mapper = KiblMapper()
    results = asyncio.run(mapper.run_mapper())
