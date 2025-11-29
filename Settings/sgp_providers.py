from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class SGPProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    regex: Optional[Dict] = None
    active: Optional[bool] = False


SGP_PROVIDERS = [
    SGPProvider(
        title="FanDuel Sportsbook",
        name="fanduel",
        url={
            "sgp_url": "https://sib.az.sportsbook.fanduel.com/api/sports/fixedodds/transactional/v1/implyBets?pricePolicy=SUGGESTED"

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
        active=True,
    ),
    SGPProvider(
        title="BetMGM Sportsbook",
        name="betmgm",
        url={
            "sgp_url": "https://www.on.betmgm.ca/cds-api/bettingoffer/picks?x-bwin-accessid=MzViOTU5Y2EtNzgyMy00ZTBmLThkNDctYjRlYjgwNjMwZDQy&lang=en-us&country=CA&userCountry=CA&subdivision=CA-Alberta"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Referer': 'https://www.on.betmgm.ca/en/sports',
            'Content-Type': 'application/json',
            'Origin': 'https://www.on.betmgm.ca',
        },
        regex={
            "event_id_regex": r"options=([\d]+)",
            "bet_id_regex": r"--(\d+)",
        },
        method="GET",
        active=True,
    ),
    SGPProvider(
        title="Fanatics Sportsbook",
        name="fanatics",
        url={
            "main_url": "wss://sportsbook.1.betfanatics.com/sportsbook-streaming-ws"
        },
        headers={
            "Accept-Encoding": "gzip,deflate",
            "Accept-Charset": "UTF-8",
            "Accept": "*/*",
            "User-Agent": "ktor-client",
        },
        regex={
            "bet_id_regex": r'"selectionId":"(\d+)"',
            "event_id_regex": r'"eventId":"(\d+)"',
        },
        method="WS",
        active=True,
    ),
    SGPProvider(
        title="Kambi Provider",
        name="kambi",
        url={
            "main_url": "https://eu1.offering-api.kambicdn.com/offering/v2018/rsicaon/onDemandPricing/event/{event_id}/outcome/{bet_ids}.json?lang=en_CA&market=CA-ON&client_id=2&channel_id=1"
        },
        regex={
            "bet_id_regex": r"single\|(\d+)\|",
            "event_id_regex": r"event/(\d+)?",
        },
        method="GET",
        active=True,
    ),
    SGPProvider(
        title="DraftKings",
        name="draftkings",
        url={
            "main_url": "https://gaming-ca-on.draftkings.com/api/wager/v1/calculateBets"
        },
        regex={
            "bet_id_regex": r"outcomes=([^\s]+)",
            # "event_id_regex": r"event/(\d+)?",
            "event_id_regex": r"outcomes=([^\s]+)",
        },
        headers={
            'x-api-features': '{EnableFullSGPDrivenFlow:true}'
        },
        method="POST",
        active=True,
    ),
    SGPProvider(
        title="HardRock",
        name="hardrock",
        url={
            "main_url": "wss://api.hardrocksportsbook.com/websocket"
        },
        regex={
            "bet_id_regex": r"betslip/(.+)",
            "event_id_regex": r"betslip/(.+)", # Use event_id same as bet_id as hardrock does not provide event_id separately
        },
        method="WS",
        active=True,
    ),
    SGPProvider(
        title="Novig",
        name="novig",
        url={
            "main_url": "https://api.novig.us/nbx/v1/parlay/request/unauthenticated"
        },
        regex={
            "bet_id_regex": r"events/([^/]+)",
            "event_id_regex": r"events/([^/]+)", # Use event_id same as bet_id as novig does not provide event_id separately
        },
        method="POST",
        active=True,
    ),
    SGPProvider(
        title="Onyx Odds",
        name="onyxodds",
        url={
            "main_url": "https://api.onyxodds.com/api/odds/parlayPrice"
        },
        regex={
            "bet_id_regex": r"selection=([\w-]+)",
            "event_id_regex": r"selection=([\w-]+)", # Use event_id same as bet_id as don't need event_id
        },
        method="POST",
        active=True,
    ),
    SGPProvider(
        title="Prophetx",
        name="prophetx",
        url={
            "main_url": "https://cash.api.prophetx.co/parlay/api/v1/affiliate/quotes",
        },
        regex={
            "bet_id_regex": r"lineID=([^&]+)",
            "event_id_regex": r"lineID=([^&]+)", # Use event_id same as bet_id as don't need event_id
        },
        headers={
            'Content-Type': 'application/json'
        },
        method="POST",
        active=True,
    )

]