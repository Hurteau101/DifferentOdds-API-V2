from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class SGPProvider:
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    regex: Optional[Dict] = None


SGP_PROVIDERS = [
    SGPProvider(
        name="fanduel_sgp",
        url={
            "league_id_url": "https://api.sportsbook.fanduel.com/sbapi/content-managed-page?page=CUSTOM&customPageId={league}&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&timezone=America%2FNew_York",
            "market_id_url": "https://api.sportsbook.fanduel.com/sbapi/event-page?_ak=FhMFpcPWXMeyZxOx&eventId={event_id}&tab=same-game-parlay-&pulseScalingEnable=true&useCombinedTouchdownsVirtualMarket=true&usePulse=true&useQuickBets=true&useQuickBetsNFL=true&useQuickBetsMLB=true",
            "sgp_url": "https://sib.nj.sportsbook.fanduel.com/api/sports/fixedodds/transactional/v1/implyBets?pricePolicy=SUGGESTED"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Sportsbook-Region': 'NJ',
            'Origin': 'https://sportsbook.fanduel.com',
            'Connection': 'keep-alive',
            'Referer': 'https://sportsbook.fanduel.com/',
            'X-Application': 'FhMFpcPWXMeyZxOx',
        },
        regex={
            "bet_id_regex": r"selectionId=([^\s]+)",
            "event_id_regex": r"marketId=([\d.]+)&",
        },
        method="GET",
    )
]