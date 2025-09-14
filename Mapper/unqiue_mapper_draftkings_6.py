import time
import requests
from dotenv import load_dotenv
import os
from Redis.redis_manager import RedisManager


class DraftKingsUniqueMapper6:
    def __init__(self):
        load_dotenv()
        self.redis = RedisManager(db=4)

    async def runner(self):
        api_key = os.getenv("BALLDONTLIE_API_KEY")
        headers = {
            "Authorization": api_key
        }

        player_dict = {}

        interation_count = 0

        def loop_pagination(next_cursor=None):
            nonlocal interation_count
            print(next_cursor)

            if interation_count == 5:
                time.sleep(60)
                interation_count = 0

            url = f"https://api.balldontlie.io/nfl/v1/players?per_page=100{f'&cursor={next_cursor}' if next_cursor else ''}"
            response = requests.get(url, headers=headers)
            print(response.status_code)
            if response.status_code == 200:
                next_cursor = response.json().get("meta", {}).get("next_cursor")
                for player in response.json().get("data"):
                    first_name = player.get("first_name", "").strip()
                    last_name = player.get("last_name", "").strip()
                    team_abbreviation = player.get("team", {}).get("abbreviation", "").strip()
                    key_name = f"{first_name[0]}. {last_name}"
                    player_dict[key_name] = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "team": team_abbreviation,
                        "position": player.get("position", "").strip(),
                    }

                if next_cursor:
                    interation_count += 1
                    print("The next cursor is:", next_cursor)
                    loop_pagination(next_cursor)

        loop_pagination()
        await self.redis.store_data("draftkings_unique_mapper_6", player_dict)



if __name__ == "__main__":
    import asyncio
    mapper = DraftKingsUniqueMapper6()
    asyncio.run(mapper.runner())