import asyncio
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from Books.Bases.pph_base import PPHBookBase
from LoggingHelper.logging_helper import insert_log, ErrorTypes
from Settings.Models.base_models import GameData, OddsFormat
from Settings.Models.sportsbooks_models import SportsbookStats
from curl_cffi import AsyncSession as CurlAsyncSession
from urllib.parse import urlencode

### NEED TO ADD BASKETBALL
VALID_PATHS = {
    # ENSURE STORE TEAM ONES ARE FIRST. (WILL ADD SORT LATER)
    "BASEBALL_MLB_Game_": {
        "market_type": "Game",
        "league": "MLB",
        "store_team": True,
    },
    "HOCKEY_NHL_Game_": {
        "market_type": "Game",
        "league": "NHL",
        "store_team": True,
    },
    "HOCKEY_HOCKEY@20;ALTER_Game_": {
        "market_type": "Game",
        "league": "NHL",
        "require_team_map": True,
    },
    "BASEBALL_MLB_1st@20;5@20;Innings_": {
        "market_type": "1st 5 Innings",
        "league": "MLB",
    },
    "BASEBALL_MLB@20;ALT@20;LINE_Game_": {
        "market_type": "Game",
        "league": "MLB",
        "require_team_map": True,
    }
}

class Buckeye1(PPHBookBase):
    def __init__(self):
        super().__init__(book_name="buckeye1")
        self.team_dict = {}

    # Need the wager int for future POST. Generated on the form page and changes every time, so we have to scrape it each time we run the book
    async def _get_wager_int(self, session: CurlAsyncSession):
        form_response = await session.get(
            "https://playnow365.com/Qubic/StraightSportSelection.php",
        )

        soup = BeautifulSoup(form_response.text, 'html.parser')
        wager_input = soup.find('input', {'name': 'inetWagerNumber'})

        if wager_input and wager_input.has_attr("value"):
            return wager_input['value']


    def line_formatter(self, line: str) -> str:
        return line.replace("½", ".5").replace("¼", ".25").replace("¾", ".75")

    def _moneyline_type(self, market_data: dict, market_name: str, league:str, **kwargs) -> SportsbookStats:
        return SportsbookStats(
            league=league,
            market=market_name,
            bet_team=market_data.get("team", ""),
            line=None,
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=float(market_data.get("odds", 0)))
        )

    def _extract_odds_line(self, grouped_str: str, has_direction: bool = False):
        format_line = self.line_formatter(grouped_str).replace('½', '.5')

        pattern = r"([ou])(\d*\.?\d+)\s+([+-]?\d*\.?\d+)" if has_direction else r"([+-]?\d*\.?\d+)\s+([+-]?\d*\.?\d+)"
        match = re.match(pattern, format_line, re.IGNORECASE)

        if not match:
            return None, None, None if has_direction else None, None

        return match.groups()



    def _total_type(self, market_data: dict, market_name: str, league: str, **kwargs) -> SportsbookStats | None:
        data = self._extract_odds_line(market_data.get("odds", ""), has_direction=True)
        if len(data) != 3:
            return None

        direction_mapper = {
            "o": "over",
            "u": "under"
        }


        raw_direction, line, odds = data[0], data[1], data[2]

        direction = direction_mapper.get(raw_direction.lower(), None)

        return SportsbookStats(
            league=league,
            market=market_name,
            bet_team=market_data.get("team", "") if kwargs.get("is_team", False) else None,
            line=float(line) if line else None,
            bet_type=direction,
            future=False,
            odds_format=OddsFormat(american_odds=float(odds) if odds else None)
        )


    def _spread_type(self, market_data: dict, market_name: str, league: str, **kwargs) -> SportsbookStats | None:
        data = self._extract_odds_line(market_data.get("odds", ""))
        if len(data) != 2:
            return None

        line, odds = data[0], data[1]

        return SportsbookStats(
            league=league,
            market=market_name,
            bet_team=market_data.get("team", ""),
            line=float(line) if line else None,
            bet_type=None,
            future=False,
            odds_format=OddsFormat(american_odds=float(odds) if odds else None)
        )


    def market_controller(self, raw_market_name: str, market_data: dict, league: str):
        mapper = {
            "moneyline": self._moneyline_type,
            "spread": self._spread_type,
            "run line": self._spread_type,
            "puck line": self._spread_type,
            "total": self._total_type,
            "team total": self._total_type
        }

        internal_converter = {
            "total points": "total",
            "money line": "moneyline"
        }

        modified_market = internal_converter.get(raw_market_name.lower(), raw_market_name).lower()
        is_team = True if modified_market in ["team total"] else False
        handler = mapper.get(modified_market.lower())


        market_type = market_data.get("market_type", "").lower()

        market_name = modified_market if market_type == "game" else f"{market_type} {modified_market}"


        if not handler:
            return None


        return handler(market_data=market_data, market_name=market_name, is_team=is_team, league=league)


    @staticmethod
    def format_date(date: str):
        """Format the date from the form 'Advance Date: 09/15 07:05PM' to ISO format in UTC timezone."""
        if not date:
            return None

        clean = re.sub(r'[\xa0\s]+', ' ', date).strip()
        parts = clean.split(' ')

        if len(parts) != 3:
            return None

        _, game_date, time = parts

        formatted_time = datetime.strptime(time, "%I:%M%p").time()
        current_year = datetime.now().year
        date_month_dt = datetime.strptime(f"{game_date}-{current_year}", "%m/%d-%Y")
        combined_date = datetime.combine(date_month_dt.date(), formatted_time, tzinfo=ZoneInfo("America/New_York"))
        utc_time = combined_date.astimezone(timezone.utc).replace(tzinfo=None)  # Remove timezone info after conversion
        return utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def clean_team(self, team_name):
        if not team_name:
            return None

        replacements = ['alt', 'rl', 'line']

        return ' '.join([part for part in team_name.lower().split() if part not in replacements]).strip()

    def _map_team(self, raw_name: str, league: str) -> str | None:
        candidates = self.team_dict.get(league, set())
        if not candidates:
            return None

        for candidate in candidates:
            if raw_name in candidate:
                return candidate

        # Fall back
        match, score, _ = process.extractOne(raw_name, candidates, scorer=fuzz.token_sort_ratio)
        return match if score >= 80 else None

    def extract_data(self, response_text: str, market_type: str, league: str, store_team: bool, require_map: bool):
        soup = BeautifulSoup(response_text, "html.parser")
        teams = soup.find_all('span', attrs={'data-language': True})

        games = []

        header_table = soup.find('tr', class_='type_title_header')

        if not header_table:
            return

        headers = [th.get_text(strip=True) for th in header_table.find_all('th')]

        for i in range(0, len(teams), 2):
            team1 = teams[i]
            team2 = teams[i + 1]

            raw_date = team1.find_parent('table').find('div', class_='opt_advance_date').get_text(strip=True)
            start_date = self.format_date(raw_date)

            team1_cells = team1.find_parent('tr').find_all('td', class_='tbl_betAmount_td')
            team2_cells = team2.find_parent('tr').find_all('td', class_='tbl_betAmount_td')

            team1_odds = {}
            team2_odds = {}

            for header, cell in zip(headers[1:], team1_cells):
                val = list(cell.strings)
                if val and val[-1].strip():
                    team1_odds[header] = val[-1].strip()

            for header, cell in zip(headers[1:], team2_cells):
                val = list(cell.strings)
                if val and val[-1].strip():
                    team2_odds[header] = val[-1].strip()


            raw_team_1_name = team1['data-language'].strip()
            raw_team_2_name = team2['data-language'].strip()

            team_1_name = self.clean_team(raw_team_1_name)
            team_2_name = self.clean_team(raw_team_2_name)

            if store_team:
                self.team_dict.setdefault(league, set()).add(team_1_name)
                self.team_dict.setdefault(league, set()).add(team_2_name)

            if require_map:
                team_1_name = self._map_team(team_1_name, league) or team_1_name
                team_2_name = self._map_team(team_2_name, league) or team_2_name

                # Use this when doing basketball, to ensure its mapping teams.
                # print(team_1_name, team_2_name)


            game_data = GameData(
                start_date=start_date,
                league=league,
                team_a=team_1_name,
                team_b=team_2_name,
                odds=[],
                game_key=self.generate_key([team_1_name, team_2_name, start_date])
            )


            for odds, team_name in [(team1_odds, team_1_name), (team2_odds, team_2_name)]:
                for market, odd in odds.items():

                    market_data = {
                        "team": team_name,
                        "odds": odd,
                        "market": market,
                        "market_type": market_type
                    }

                    # Use this for debugging when doing baskebtall
                    # print(market_data)

                    market_stats = self.market_controller(
                        raw_market_name=market,
                        market_data=market_data,
                    )

                    if market_stats:
                        game_data.odds.append(market_stats)

            if game_data.odds:
                games.append(game_data)

        return games


    async def run_book(self) -> list | None:
        cookies = await self.auth_redis_manager.get_data(self.auth_id_name)

        if not cookies:
            return

        async with CurlAsyncSession(impersonate="safari15_5", cookies=cookies) as session:
            wager_int = await self._get_wager_int(session)
            if not wager_int:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.MISC,
                    error_message="No wager details found"
                )
                return None

            tasks = [
                session.post(
                    url=self.book_data.url.get("market_url"),
                    headers=self.book_data.headers,
                    data=urlencode({
                        'keyword_search': '',
                        'inetWagerNumber': str(wager_int),
                        'inetSportSelection': 'sport',
                        'contestType1': '',
                        'contestType2': '',
                        'contestType3': '',
                        market: 'on'
                    })
                )

                for market in VALID_PATHS
            ]

            semaphore = asyncio.Semaphore(2)

            results = await asyncio.gather(*[
                self.post_with_semaphore(semaphore, task) for task in tasks
            ])

            if not results:
                insert_log(
                    book_name=self.book_data.title,
                    error_type=ErrorTypes.API_NO_DATA,
                    error_message="No data returned from API"
                )
                return None

            event_data = {}

            for result, market in zip(results, VALID_PATHS.values()):
                result.encoding = 'utf-8'

                game_data = self.extract_data(response_text=result.text, market_type=market['market_type'], league=market['league'],
                                              store_team=market.get('store_team', False), require_map=market.get('require_team_map', False))

                if not game_data:
                    continue

                for game in game_data:
                    self.add_to_events(event_data, game, GameData)

            buckeye_data = list(event_data.values())

            await self.store_data(
                data_to_store=buckeye_data,
                key_name=self.book_data.name
            )

            await self.flush_unmapped()
            return buckeye_data



if __name__ == "__main__":
    buck = Buckeye1()
    asyncio.run(buck.run_book())

