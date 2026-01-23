import asyncio
from datetime import date, datetime, timedelta
import aiohttp
import orjson
from old.Mapper.static_mapper import LEAGUES


class ESPNMapper:
    SPORTS = {
        "nfl": "football",
        "nba": "basketball",
        "mlb": "baseball",
        "nhl": "hockey",
        "college-football": "football",
        "mens-college-basketball": "basketball",
        "wnba": "basketball",
        "womens-college-basketball": "basketball"
    }
    def __init__(self, start_date: str | date | datetime | None = None, end_date: str | date | datetime | None = None):
        self.start_date = self._validate_date(start_date)
        self.end_date = self._validate_date(end_date)

        if not self.start_date:
            self.start_date = self._create_date(start_date=True, end_date=False)

        if not self.end_date:
            self.end_date = self._create_date(start_date=False, end_date=True)


    def _validate_date(self, date_passed_in):
        if isinstance(date_passed_in, str):
            try:
                return datetime.strptime(date_passed_in, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        elif isinstance(date_passed_in, datetime):
            return date_passed_in.strftime("%Y%m%d")
        else:
            return None

    def _create_date(self, end_date: bool, start_date: bool):
        if end_date and start_date:
            raise ValueError("Cannot set both start_date and end_date to True")

        current_date = date.today()

        if end_date:
            raw_end = current_date + timedelta(days=7)
            return raw_end.strftime("%Y%m%d")


        if start_date:
            return current_date.strftime("%Y%m%d")

    def _filter_games(self, events, league_data):
        filtered_data = {}

        sides = ["home", "away"]

        league = next((
            league.get("abbreviation")
            for league in league_data
        ), None)

        if not league:
            return None

        for event in events:
            league = LEAGUES.get(league.lower(), league.lower())
            game_date = event.get("date")
            date_obj = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            date_only = date_obj.date().strftime("%Y-%m-%d")

            competition = event.get("competitions", [])[0] if event.get("competitions") else {}
            competitors = competition.get("competitors", [])

            game_key = f"_vs_".join(sorted([
                competitor.get("team", {}).get("displayName").lower()
                for competitor in competitors
                if competitor.get("homeAway").lower() in sides if competitor.get("homeAway") and competitor.get("team")
            ])).replace(" ", "_")

            filtered_data.update({f"{game_key}_{league}_{date_only}".lower(): game_date})


        return filtered_data

    async def fetch(self, session, league, sport, url=None):
        if not url:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={self.start_date}-{self.end_date}"

        retry_count = 0

        async def api_caller(url):
            nonlocal retry_count
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404 and retry_count < 1:
                    retry_count += 1
                    new_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
                    return await api_caller(new_url)
                return None

        return await api_caller(url)

    async def get_games(self):
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch(session=session, league=league, sport=sport)
                for league, sport in ESPNMapper.SPORTS.items()
            ]

            responses = await asyncio.gather(*tasks)

            filtered_data = {
                game_key: game_date
                for response in responses
                if response
                for game_key, game_date in self._filter_games(response.get("events", []), response.get("leagues")).items()
            }

            return filtered_data


if __name__ == "__main__":
    current_date = datetime.now()
    mapper = ESPNMapper()
    games = asyncio.run(mapper.get_games())
    if games:
        from old.Redis.redis_manager import RedisSync
        redis = RedisSync(db=2)
        redis.set("espn_games", orjson.dumps(games), ex=90000)
