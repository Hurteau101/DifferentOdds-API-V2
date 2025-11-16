from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class SportsbookProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    active: Optional[bool] = False


SPORTSBOOK_PROVIDERS = [
    SportsbookProvider(
        title="Ace Sportsbook",
        name="aces",
        url={
            "login_url": "https://backend.betvegas23.com/Login.aspx",
            "league_list_url": "https://backend.betvegas23.com/wager/ActiveLeaguesHelper.aspx?WT=0",
            "games_url": "https://backend.betvegas23.com/wager/NewScheduleHelper.aspx?WT=0&lg={league_id}"
        },
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://betvegas23.com",
            "Referer": "https://betvegas23.com/",
        },
        method="GET",
        active=True
    )
]