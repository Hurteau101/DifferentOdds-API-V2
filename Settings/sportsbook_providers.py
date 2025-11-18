import os
from dataclasses import dataclass
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SportsbookProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    active: Optional[bool] = False


SPORTSBOOK_PROVIDERS = [
    # SportsbookProvider(
    #     title="Ace Sportsbook",
    #     name="aces",
    #     url={
    #         "login_url": "https://backend.betvegas23.com/Login.aspx",
    #         "league_list_url": "https://backend.betvegas23.com/wager/ActiveLeaguesHelper.aspx?WT=0",
    #         "games_url": "https://backend.betvegas23.com/wager/NewScheduleHelper.aspx?WT=0&lg={league_id}"
    #     },
    #     headers={
    #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    #         "Content-Type": "application/x-www-form-urlencoded",
    #         "Origin": "https://betvegas23.com",
    #         "Referer": "https://betvegas23.com/",
    #     },
    #     method="GET",
    #     active=True
    # ),
    SportsbookProvider(
        title="STG",
        name="stg",
        url={
            "login_url": "https://bettheguys.com/Login.aspx",
            "league_list_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuMainHeaders",
            "league_section": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuLeaguesWithOpenGames",
            "game_markets": "https://bettheguys.com/Player/app/services/linesAJX.aspx/GetLines"
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://bettheguys.com",
        },
        method="POST",
        active=True

    ),
    SportsbookProvider(
        title="1BV",
        name="1bv",
        url={
            "login_url": "https://everygame247.com/Security/ValidateCredentials",
            "league_list_url": "https://everygame247.com/Actions/api/Menu/GetMenu",
            "player_token_url": "https://everygame247.com/Actions/api/Login/PlayerLogin?",
            "game_markets": "https://everygame247.com/Actions/api/Event/GetEvent"

        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://everygame247.com',
            'Connection': 'keep-alive',
            "appToken": os.getenv("BETVEGAS_APP_TOKEN")
        },
        method="POST",
        active=True

    )

]