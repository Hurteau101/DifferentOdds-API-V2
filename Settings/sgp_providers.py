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
    ),
    SGPProvider(
        title="The Score",
        name="thescore",
        url={
            "anonymous_token_url": "https://sportsbook.ca-default.thescore.bet/graphql/persisted_queries/e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382?extensions=%7B%22clientLibrary%22:%7B%22name%22:%22apollo-ios%22,%22version%22:%221.21.0%22%7D,%22persistedQuery%22:%7B%22sha256Hash%22:%22e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382%22,%22version%22:1%7D%7D&operationName=Startup&variables=%7B%22connectToken%22:null,%22globalRedirect%22:false,%22isMedia%22:false,%22latLongParams%22:%7B%22accuracy%22:35,%22latitude%22:51.166784592498459,%22longitude%22:-114.14382905748789%7D,%22logoHeight%22:24,%22toolbarIconMaxHeight%22:20%7D",
            "graph_url": "https://sportsbook.ca-default.thescore.bet/graphql",
        },
        headers={
            "User-Agent": "theScore Bet/25.23.2 iPadOS/17.7.10 (iPhone; Retina, 750x1334, mobile)",
            "x-platform": "ios",
        },
        method="POST",
        active=True,
    ),
    SGPProvider(
        title="Caesars Sportsbook",
        name="caesars",
        url={
            "main_url": "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb/v2/bets/details"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'content-type': 'application/json',
            'X-Unique-Device-Id': '53c26028-d052-4871-83e7-a6cbf3686f57',
            'X-Platform': 'cordova-desktop',
            'X-App-Version': '7.38.0',
        },
        regex={
            "bet_id_regex": r'selectionIds=([0-9a-fA-F-]+)', # bet_id will be the selection_id
            "event_id_regex": r'selectionIds=([0-9a-fA-F-]+)',  # Use event_id same as bet_id as don't need event_id
        },
        method="POST",
        active=True,
    )

]