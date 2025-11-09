from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class SGPMapperProviders:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None

SGP_MAPPER_PROVIDERS = [
    SGPMapperProviders(
        title="FanDuel Sportsbook",
        name="fanduel",
        url={
            "event_id_url": "https://api.sportsbook.fanduel.com/ips/stats/eventIds",
            "sgp_markets": "https://api.sportsbook.fanduel.com/sbapi/event-page?_ak=FhMFpcPWXMeyZxOx&eventId={event_id}&tab=same-game-parlay-&",
            "additional_id_url": "https://api.sportsbook.fanduel.com/sbapi/content-managed-page?_ak=FhMFpcPWXMeyZxOx&page=SPORT&eventTypeId={event_type}"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Sportsbook-Region': 'AZ',
        },
        method="GET",
    ),
    SGPMapperProviders(
        title="Onyx Sportsbook",
        name="onyx",
        url={
            "league_url": "https://api.onyxodds.com/api/odds/mainLines",
            "game_ids_url": "https://api.onyxodds.com/api/odds/mainLines/{league_name}",
            "market_url": "https://api.onyxodds.com/api/odds/gameMainLines/{game_id}",
        },
        method="GET",
    ),
    SGPMapperProviders(
        title="BetMGM Sportsbook",
        name="betmgm",
        url={
            "market_id_url": "https://www.on.betmgm.ca/cds-api/bettingoffer/fixtures?x-bwin-accessid=MzViOTU5Y2EtNzgyMy00ZTBmLThkNDctYjRlYjgwNjMwZDQy&lang=en-us&country=CA&userCountry=CA&subdivision=CA-Alberta&fixtureTypes=Standard&state=Latest&offerMapping=All&offerCategories=Gridable&fixtureCategories=Gridable,NonGridable,Other&sportIds={league_id}&regionIds=&competitionIds=&conferenceIds=",
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Referer': 'https://www.on.betmgm.ca/en/sports',
            'Content-Type': 'application/json',
            'Origin': 'https://www.on.betmgm.ca',
        },
        method="GET",
    )
]