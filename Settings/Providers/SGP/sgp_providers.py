from typing import Optional
from Settings.Providers.base_provider import BaseProvider
from dataclasses import dataclass

@dataclass
class SGPMapper:
    url: dict
    method: str
    headers: Optional[dict] = None
    is_active: Optional[bool] = False


@dataclass
class SGPProvider(BaseProvider):
    regex: Optional[dict] = None
    mapping: Optional[SGPMapper] = None

SGP_PROVIDERS = [
    SGPProvider(
        title="FanDuel Sportsbook",
        name="fanduel",
        url={
            "sgp_url": "https://sib.az.sportsbook.fanduel.com/api/sports/fixedodds/transactional/v1/implyBets?pricePolicy=SUGGESTED"

        },
        regex={
            "bet_id": r"selectionId=([^\s]+)",
            "event_id": r"marketId=([\d.]+)&",
        },
        headers={
            'Origin': 'https://sportsbook.fanduel.com',
            'Connection': 'keep-alive',
            'Referer': 'https://sportsbook.fanduel.com/',
            'X-Application': 'FhMFpcPWXMeyZxOx',
        },
        method="GET",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
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
            is_active=True
        )
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
            # "event_id": r"options=([\d]+)",
            # "event_id": r"options=[^&]*-(\d+)-+\d+(?:&|$)",


            "bet_id": r"options=[^&]*?-\d+-+(\d+)"
            # "bet_id": r"options=[^&]*-(\d+)-+\d+(?:&|$)"
        },
        method="GET",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
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
            is_active=True
        )
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
            "selection_id": r'"selectionId":"(\d+)"',
        },
        method="WS",
        has_sgp=True,
        is_active=True,
    ),
    SGPProvider(
        title="Kambi Provider",
        name="kambi",
        url={
            "main_url": "https://eu1.offering-api.kambicdn.com/offering/v2018/rsicaon/onDemandPricing/event/{event_id}/outcome/{bet_ids}.json?lang=en_CA&market=CA-ON&client_id=2&channel_id=1"
        },
        regex={
            "bet_id": r"single\|(\d+)\|",
            "event_id": r"event/(\d+)?",
        },
        method="GET",
        has_sgp=True,
        is_active=True,
    ),
    SGPProvider(
        title="DraftKings",
        name="draftkings",
        url={
            "main_url": "https://gaming-us-va.draftkings.com/api/wager/v1/calculateBets"
        },
        regex={
            "outcome_id": r"outcomes=([^\s]+)",
        },
        headers={
              'User-Agent': 'dksb/5.47.0 (iOS; iPad7,6; iOS17.7.11)',
              'X-Client-Name': 'DraftKings',
              'X-Api-Features': '{ "EnableFullSGPDrivenFlow": true }',
              'Accept': 'application/json',
              'Content-Type': 'application/json',
        },
        method="POST",
        has_sgp=True,
        is_active=True,
    ),
    SGPProvider(
        title="HardRock",
        name="hardrock",
        url={
            "main_url": 'wss://api.hardrocksportsbook.com/websocket'
        },
        regex={
            "bet_id": r"betslip/(.+)",
        },
        method="WS",
        is_active=True,
        has_sgp=True,
        alternate_name="hard rock"
    ),
    SGPProvider(
        title="Novig",
        name="novig",
        url={
            "main_url": "https://api.novig.us/nbx/v1/parlay/request/unauthenticated"
        },
        regex={
            "event_id": r"events/([^/]+)",
        },
        method="POST",
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'Origin': 'https://novig.com',
            'Connection': 'keep-alive',
            'Referer': 'https://novig.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'TE': 'trailers'
        },
        is_active=True,
        has_sgp=True,
    ),
    SGPProvider(
        title="Onyx Odds",
        name="onyx odds",
        url={
            "main_url": "https://api.onyxodds.com/api/odds/parlayPrice"
        },
        regex={
            "selection_id": r"selection=([\w-]+)",
        },
        method="POST",
        is_active=True,
        has_sgp=True,
        alternate_name="onyx odds",
        mapping=SGPMapper(
            url={
                "league_url": "https://api.onyxodds.com/api/odds/mainLines",
                "game_ids_url": "https://api.onyxodds.com/api/odds/mainLines/{league_name}",
                "market_url": "https://api.onyxodds.com/api/odds/gameMainLines/{game_id}",
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://app.onyxodds.com/',
                'Content-type': 'application/json',
                'traceparent': '00-0000000000000000b6dc9e1054659cdb-689b4decdb0e86b3-01',
                'x-datadog-origin': 'rum',
                'x-datadog-parent-id': '7537704081017439923',
                'x-datadog-sampling-priority': '1',
                'x-datadog-trace-id': '13176580402751839451',
                'Origin': 'https://app.onyxodds.com',
                'Connection': 'keep-alive',
            },
            method="GET",
            is_active=True
        )
    ),
    SGPProvider(
        title="Prophetx",
        name="prophet x",
        url={
            "main_url": "https://cash.api.prophetx.co/parlay/api/v1/affiliate/quotes",
        },
        regex={
            "line_id": r"lineID=([^&]+)",
        },
        headers={
            'Content-Type': 'application/json'
        },

        method="POST",
        is_active=True,
        has_sgp=True,
        alternate_name="prophet x",
    ),
    SGPProvider(
        title="The Score",
        name="thescore",
        url={
            # "anonymous_token_url": "https://sportsbook.ca-default.thescore.bet/graphql/persisted_queries/e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382?extensions=%7B%22clientLibrary%22:%7B%22name%22:%22apollo-ios%22,%22version%22:%221.21.0%22%7D,%22persistedQuery%22:%7B%22sha256Hash%22:%22e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382%22,%22version%22:1%7D%7D&operationName=Startup&variables=%7B%22connectToken%22:null,%22globalRedirect%22:false,%22isMedia%22:false,%22latLongParams%22:%7B%22accuracy%22:35,%22latitude%22:51.166784592498459,%22longitude%22:-114.14382905748789%7D,%22logoHeight%22:24,%22toolbarIconMaxHeight%22:20%7D",
            "anonymous_token_url": "https://sportsbook.ca-default.thescore.bet/graphql/persisted_queries/e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382?extensions=%7B%22clientLibrary%22:%7B%22name%22:%22apollo-ios%22,%22version%22:%221.21.0%22%7D,%22persistedQuery%22:%7B%22sha256Hash%22:%22e8fa300a9384c89576e6bec55cf1a4fc97a3e15255571cf9f841515abfb7c382%22,%22version%22:1%7D%7D&operationName=Startup&variables=%7B%22connectToken%22:null,%22globalRedirect%22:false,%22isMedia%22:false,%22latLongParams%22:%7B%22accuracy%22:35,%22latitude%22:40.7128,%22longitude%22:-74.0060%7D,%22logoHeight%22:24,%22toolbarIconMaxHeight%22:20%7D",
            "draftbet_url": "https://sportsbook.us-default.thescore.bet/graphql/persisted_queries/11b043d75b61c332daff19bff740fb035a524d6d0fe9d12debc729c667633b61",
            "sgp_url": "https://sportsbook.us-default.thescore.bet/graphql/persisted_queries/11b043d75b61c332daff19bff740fb035a524d6d0fe9d12debc729c667633b61"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-CA,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': 'https://sportsbook.thescore.bet/',
            'content-type': 'application/json',
            'apollographql-client-name': 'espnbet-espnbet-web',
            'apollographql-client-version': '26.1.0',
            'x-platform': 'web',
            'x-app-version': '26.1.0',
            'x-app': 'espnbet',
            'x-client': 'espnbet',
            'x-datadog-origin': 'rum',
            'Origin': 'https://sportsbook.thescore.bet',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        },
        method="POST",
        is_active=True,
        has_sgp=True,
    ),
    SGPProvider(
        title="Caesars Sportsbook",
        name="caesars",
        url={
            "main_url": "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb/v2/bets/details"
        },
        headers={
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            # 'Accept': '*/*',
            # 'Accept-Language': 'en-US,en;q=0.5',
            # 'Accept-Encoding': 'gzip, deflate, br, zstd',
            # 'content-type': 'application/json',
            # 'X-Unique-Device-Id': '53c26028-d052-4871-83e7-a6cbf3686f57',
            # 'X-Platform': 'cordova-desktop',
            # 'X-App-Version': '7.38.0',
            'Host': 'api.americanwagering.com',
            'X-AppBranding': 'Liberty',
            'tracestate': '2185826@nr=0-2-2619101-594413108-a602d6bf08fe0181---1782352408140',
            'Accept': 'application/json',
            'x-njd-sportsbook-app-env': 'SAXpvdRTmGTB',
            'newrelic': 'ewoiZCI6IHsKImFjIjogIjI2MTkxMDEiLAoiYXAiOiAiNTk0NDEzMTA4IiwKImlkIjogImE2MDJkNmJmMDhmZTAxODEiLAoidGkiOiAxNzgyMzUyNDA4MTQwLAoidGsiOiAiMjE4NTgyNiIsCiJ0ciI6ICI3Y2MzOGFhNTNkNmUyNjkzOTQ1NTZjZmQxZjUyYTNhZCIsCiJ0eSI6ICJNb2JpbGUiCn0sCiJ2IjogWwowLAoyCl0KfQ==',
            'X-App-GUID': '82A3A0BB-A934-4631-A729-68BDDD1318FC',
            'Accept-Language': 'en-gb',
            'User-Agent': 'us.williamhill.nj.sports/7.49.2',
            'Connection': 'keep-alive',
            'X-Unique-Device-Id': 'D3CCE48A-FAEB-429E-95FD-00F1F82C026F',
            'X-App-Version': '7.49.2.4017',
            'X-Platform': 'native-ios',
            'traceparent': '00-7cc38aa53d6e269394556cfd1f52a3ad-a602d6bf08fe0181-01',
            'Content-Type': 'application/json'
        },
        regex={
            "select_id": r'selectionIds=([0-9a-fA-F-]+)',
        },
        method="POST",
        is_active=False,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "event_url": "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb/v4/sports/{sport}/tabs",
                "game_url": "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb/v4/events/{event_id}?useEventPayloadWithTabNav=true",
                "market_url": "https://api.americanwagering.com/regions/us/locations/az/brands/czr/sb{path}",
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://sportsbook.caesars.com/',
                'content-type': 'application/json',
                'x-app-version': '7.41.0',
                'x-platform': 'cordova-desktop',
                'x-unique-device-id': '53c26028-d052-4871-83e7-a6cbf3686f57',
                'Origin': 'https://sportsbook.caesars.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site',
            },
            method="GET",
            is_active=False
        )
    ),
    SGPProvider(
        title="Betonline",
        name="betonline",
        url={
            "sgp_url": ""
        },
        headers={

        },
        method="GET",
        is_active=False,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "sports_url": "https://api-offering.betonline.ag/api/offering/sgp/sports",
                "leagues_url": "https://api-offering.betonline.ag/api/offering/sgp/leagues",
                "events_url": "https://api-offering.betonline.ag/api/offering/sgp/events",
                "market_labels_url": "https://public-prod-gen2.sportcastlive.com/public/getmarketsV2/"
                # "teams_url": "https://public-prod-gen2.sportcastlive.com/public/GetFixture/"
                # "mapping_url": "https://public-prod-gen2.sportcastlive.com/public/getmarketsV2/"
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                'Accept-Encoding': 'gzip, deflate',
                "Referer": "https://www.betonline.ag/",
                "Content-Type": "application/json",
                "gsetting": "bolnasite",
                "utc-offset": "360",
                "Origin": "https://www.betonline.ag",
            },
            method="POST",
            is_active=False
        )
    ),
    SGPProvider(
        title="Betway",
        name="betway",
        url={
            "sgp_url": "https://betway.com/g/api/betting/betedge/row/betfactory/api/generatebets"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'x-correlation-id': 'f56ef3e5-8cbe-4b8d-b1e1-83db6f1f798b',
            'Origin': 'https://betway.com',
            'Connection': 'keep-alive',
        },
        method="GET",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "category_names": "https://betway.com/g/services/api/Content/v1/GetMenus",
                "category_url": "https://betway.com/g/services/api/events/v2/GetCategoryDetails",
                "events_url": "https://betway.com/g/services/api/events/v2/GetGroup",
                "event_details": "https://betway.com/g/services/api/events/v2/GetEventDetails"
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'Origin': 'https://betway.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Priority': 'u=0',
                'TE': 'trailers'
            },
            method="POST",
            is_active=True
        )
    ),
    SGPProvider(
        title="Stake",
        name="stake",
        url={
            "sgp_url": ""
        },
        headers={

        },
        method="GET",
        is_active=False,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "general_url": "https://stake.com/_api/graphql",
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0)',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip',
                'Referer': 'https://stake.com/sports/home',
                'access-control-allow-origin': '*',
                'content-type': 'application/json',
                'x-language': 'en',
                'x-operation-name': 'SportIndex',
                'x-operation-type': 'query',
                'Origin': 'https://stake.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Priority': 'u=4',
                'TE': 'trailers',
            },
            method="POST",
            is_active=False
        )
    ),
    SGPProvider(
        title="Fliff Sportsbook",
        name="fliff",
        url={
            "sgp_url": "https://m-c811.app.getfliff.com/fc_mobile_api_private"
        },
        headers={
            'accept': 'application/json, text/plain, */*',
            'x-dd-request-code': 'access_token_auth',
            'content-type': 'application/json',
            'user-agent': 'okhttp/4.10.0'
        },
        regex={
            "event_id": r"eventId=([^&]+)",
        },
        method="POST",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "main_url": "https://herald-2.app.getfliff.com/fc_mobile_api_public",
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Content-Type': 'application/json',
                'Origin': 'https://sports.getfliff.com',
                'Connection': 'keep-alive',
                'Referer': 'https://sports.getfliff.com/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            },
            method="POST",
            is_active=True
        )
    ),
    SGPProvider(
        title="Bovada Sportsbook",
        name="bovada",
        url={
            "sgp_url": "https://services.ozoon.eu/services/sports/bet/betslip"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': 'https://services.ozoon.eu/',
            'content-type': 'application/json',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'same-origin',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=4',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'TE': 'trailers',
        },
        regex={
            "event_id": r"sports\/(.+)"
        },
        method="GET",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "main_url": "https://www.bovada.lv/services/sports/event/coupon/events/A/description/",
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Referer': 'https://services.ozoon.eu/',
                'content-type': 'application/json',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'same-origin',
                'Sec-Fetch-Site': 'same-origin',
                'Priority': 'u=4',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
                'TE': 'trailers',
            },
            method="GET",
            is_active=True
        )
    ),

    SGPProvider(
        title="Rebet",
        name="rebet",
        url={
            "sgp_url": ""
        },
        headers={},
        regex={
        },
        method="GET",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "leagues_url": "https://d18egz9kdmewpc.cloudfront.net/sportsbook/v3/all-sports",
                "events_url": "https://d18egz9kdmewpc.cloudfront.net/sportsbook/v3/events",
                "market_urls": "https://d18egz9kdmewpc.cloudfront.net/sportsbook/v3/events/{event_id}"
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'x-api-key': 'J9xowBQZM980G97zv9VoB9Ylady1pVtS5Ix9tuL1', # Public API key, fine if exposed.
                'Origin': 'https://play.rebet.app',
                'Connection': 'keep-alive',
                'Referer': 'https://play.rebet.app/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site'
            },
            method="GET",
            is_active=True
        )
    ),
    SGPProvider(
        title="Prop Builder",
        name="prop_builder",
        url={
            "sgp_url": "https://bv2-us.digitalsportstech.com/api/v2/odds/acca"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, zstd',
            'Origin': 'https://troya.xyz',
            'Connection': 'keep-alive',
            'Referer': 'https://troya.xyz/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site'
        },
        regex={
        },
        method="POST",
        is_active=True,
        has_sgp=True,
        mapping=SGPMapper(
            url={
                "league_url": "https://bv2-us.digitalsportstech.com/api/sgmLeagues?sb=betus&user=undefined&legacy=1",
                "game_url": "https://bv2-us.digitalsportstech.com/api/sgmGames?sb=betus",
                "market_url": "https://bv2-us.digitalsportstech.com/api/grouped-markets/v2/map?sb=betus&legacy=1",
                "props_base": "https://bv2-us.digitalsportstech.com/api/",
                "game_details_url": "https://bv2-us.digitalsportstech.com/api/gfm/gamesByGfm"
            },
            headers={
            },
            method="GET",
            is_active=True
        )
    ),
]


