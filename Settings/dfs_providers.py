import os
from dataclasses import dataclass
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

# DFSProvider class to represent a DFS provider with its details.
@dataclass
class DFSProvider:
    title: str
    name: str
    url: dict
    method: str
    headers: Optional[Dict] = None
    active: Optional[bool] = False
    # payload_list: Optional[List[Dict]] = None

# List of DFS providers with their configurations.
DFS_PROVIDERS = [
    DFSProvider(
        title="Underdog Fantasy",
        name="underdog",
        url={
            "main_url": "https://api.underdogfantasy.com/beta/v6/over_under_lines",
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="PrizePicks",
        name="prizepicks",
        url={
            "main_url": "https://partner-api.prizepicks.com/projections"
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Betr",
        name="betr",
        url={
            "main_url": "https://api.fantasy.betr.app/graphql",
        },
        method="POST",
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
            'Accept': 'application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Referer': 'https://picks.betr.app/',
            'fantasy-api-version': '11.0',
            'fantasy-application-version': '3.26.6',
            'jurisdiction': 'IL',
            'channel': 'WEB',
            'authorization': '',
            'content-type': 'application/json',
            'Origin': 'https://picks.betr.app',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Priority': 'u=4',
            'TE': 'trailers'
        },
        active=True
    ),
    DFSProvider(
        title="Drafters",
        name="drafters",
        url={
            "main_url": "https://node.drafters.com/props-game/get-props-games/",
            "alternate_url": "https://api.drafters.com/games/list/draft_user?page_type=props"
        },
        headers={
            "Authorization": os.getenv("drafters_auth_token"),
            "Accept": "application/json",
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Boom Fantasy",
        name="boom",
        url={
            "main_url": "https://production-boom-dfs-backend-api.boomfantasy.com/api/v1/contests/multiLine/99708fb7-167a-4314-b69d-e38dc782a63a?questionStatus=available&renderType=multiLine"
        },
        headers={
            "Authorization": os.getenv("boom_auth_token"),
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="ParlayPlay",
        name="parlayplay",
        url={
            "main_url": "http://45.61.52.251:8000/parlayplay"
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Splash Sports",
        name="splashsports",
        url={
            "main_url": "https://api.splashsports.com/props-service/api/props?limit=1000&offset=0"
        },
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Authorization": os.getenv("splash_auth_token"),
        },
        method="GET",
        active=False
    ),
    DFSProvider(
        title="Ownerbox",
        name="ownerbox",
        url={
            "main_url": "https://app.ownersbox.com/fsp/v4/market?sport={league}",
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'OwnersBox-Client-Type': 'web',
            'OwnersBox-Client-Version': '1.11.4',
            'Connection': 'keep-alive',
            'Referer': 'https://app.ownersbox.com/wfs/player-picks/lobby/MLB',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers',
            'Cookie': f'obauth={os.getenv("ownerbox_auth_token")}'
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Parlaye",
        name="parlaye",
        url={
            "main_url": "https://m2efyeevmf.us-east-2.awsapprunner.com/available_picks/get-player-picks/"
        },
        method="POST",
        active=True
    ),
    DFSProvider(
        title="DraftKings Pick 6",
        name="draftkings_6",
        url= {
            "main_url": "https://pick6.draftkings.com/?sport={league}&_data=routes%2F_homeShared",
            "alternate_url": "https://pick6.draftkings.com/?_data=routes%2F_homeShared"
        },
        headers={
            'Referer': 'https://pick6.draftkings.com/?_gl=1*v93w3x*_gcl_au*ODkyNzA4NDI2LjE3NTUxOTA2OTc.*_ga*MTU4MjI5MzIxLjE3MzgwNDQ1ODU.*_ga_QG8WHJSQMJ*czE3NTUzNTMyMDAkbzI0JGcxJHQxNzU1MzUzMjA2JGo1NCRsMCRoMA..',
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Sleeper Fantasy",
        name="sleeper",
        url={
            "main_url": "https://api.sleeper.app/lines/available?sports[]all&include_preseason=true",  # Main Lines
            "alternate_url": "https://api.sleeper.app/lines/available_alt?sports[]all&include_preseason=true",# Alternate Lines
            "alternate_url_2": "https://api.sleeper.app/scores",  # Game Data
            "alternate_url_3": "https://api.sleeper.app/players/?exclude_injury=true",  # Player Data
            'alternate_url_4': "https://api.sleeper.app/scores/lines_game_picker",  # Season Data
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Dabble",
        name="dabble",
        url={
            "main_url": "https://api.dabble.com/competitions/active/", # Leagues
            "alternate_url": "https://api.dabble.com/competitions/{league_id}/sport-fixtures?exclude[]=markets&exclude[]=selections&exclude[]=prices", # Game Ids
            "alternate_url_2": "https://api.dabble.com/sportfixtures/details/{game_id}?filter=dfs-enabled",
        },
        method="GET",
        active=True
    ),
    DFSProvider(
        title="Chalkboard",
        name="chalkboard",
        url={
            "main_url": "https://firestore.googleapis.com/v1/projects/taild-262305/databases/(default)/documents:runQuery"
        },
        headers={
            'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6ImUzZWU3ZTAyOGUzODg1YTM0NWNlMDcwNTVmODQ2ODYyMjU1YTcwNDYiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vdGFpbGQtMjYyMzA1IiwiYXVkIjoidGFpbGQtMjYyMzA1IiwiYXV0aF90aW1lIjoxNzU3NDI4MDUzLCJ1c2VyX2lkIjoidFp5eVd2djNQQ1Ewdk4xTnNTcnE5elhXZVlHMyIsInN1YiI6InRaeXlXdnYzUENRMHZOMU5zU3JxOXpYV2VZRzMiLCJpYXQiOjE3NTc2MzYyMjEsImV4cCI6MTc1NzYzOTgyMSwiZW1haWwiOiJ0NzY4MTk5MkBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZW1haWwiOlsidDc2ODE5OTJAZ21haWwuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoicGFzc3dvcmQifX0.NC7hcNcjLTgvFEsYPnQjzsW63EbNKIicyGZyjJ4xmBICcy51X1tKtJpmeSLtyLnSHfN7MwdVeiYXYxrSBBQzQ0m_6fpot21igxebR2WfonnuzJS5tIJ_udPHSFdLoGARX3WrNSGRyCb3AW2u6nHvZ5juRKknNJtG847334-YUjhJTScvhH-j4ZUoIHtH2SizqUzzUH9dzBOkqOhn8pz8GsY-i4w4iUTcLrboGPRWgndD4V8-FGFDEpcYSlKznQDfGR405mP_iDE45G2UitXzc8N5pjjkvicNDs2cU6iwovW6X3PStGiNF-OeX3_ytlmZ3eNiLe_Ackr_U2dfptYMWg'
        },
        method="POST",
        active=True
    ),
    DFSProvider(
        title="FanDuel Picks",
        name="fanduel_picks",
        url={
            "main_url": "https://picks.fanduel.com/lobby?sport={league}&_data=routes%2Flobby%2B%2F_route",
            "stat_url": "https://picks.fanduel.com/api/game-group-props?gameGroupId={game_id}&marketIds=&_data=routes%2Fapi%2B%2Fgame-group-props%2B%2F_resource"
        },
        headers={
            'Host': 'picks.fanduel.com',
            'Sec-Fetch-Site': 'same-origin',
            'Connection': 'keep-alive',
            'Sec-Fetch-Mode': 'cors',
            'Accept': '*/*',
            'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_7_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 AppInfo (appDomain/picks; version/3.1.0; platform/ios)',
            'Referer': 'https://picks.fanduel.com/signin',
            'Sec-Fetch-Dest': 'empty',
            'Accept-Language': 'en-CA,en-US;q=0.9,en;q=0.8',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
            'Content-Type': 'application/json',
        },
        method="GET",
        active=True
    )
]