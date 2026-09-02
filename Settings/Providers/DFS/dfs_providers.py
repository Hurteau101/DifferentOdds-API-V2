import os
from dataclasses import dataclass
from dotenv import load_dotenv
from Settings.Providers.base_provider import BaseProvider, AuthJobDict, RedisSelector, APSchedulerDetails

load_dotenv()

@dataclass
class DFSProvider(BaseProvider):
    base_file_path = "Books.DFS"
    base_interval = 180


# List of DFS providers with their configurations.
DFS_PROVIDERS = [
    DFSProvider(
        title="Underdog Fantasy",
        name="underdog",
        url={
            "main_url": "https://api.underdogfantasy.com/beta/v6/over_under_lines",
        },
        method="GET",
        is_active=True,
        class_name="Underdog",
        file_name="underdog",
    ),
    DFSProvider(
        title="PrizePicks",
        name="prizepicks",
        url={
            "main_url": "https://partner-api.prizepicks.com/projections"
        },
        method="GET",
        is_active=True,
        class_name="Prizepicks",
        file_name="prizepicks",
    ),
    DFSProvider(
        title="Betr",
        name="betr",
        url={
            "main_url": "https://api.fantasy.betr.app/graphql",
        },
        method="POST",
        headers={
            'Referer': 'https://picks.betr.app/',
            'fantasy-api-version': '11.0',
            'fantasy-application-version': '3.26.6',
            'jurisdiction': 'IL',
            'channel': 'WEB',
            'authorization': '',
            'content-type': 'application/json',
            'Origin': 'https://picks.betr.app',
            'Connection': 'keep-alive',
            'TE': 'trailers'
        },
        is_active=True,
        class_name="Betr",
        file_name="betr",
    ),
    DFSProvider(
        title="Drafters",
        name="drafters",
        url={
            "main_url": "https://node.drafters.com/props-game/get-props-games/",
            "alternate_url": "https://api.drafters.com/games/list/draft_user?page_type=props"
        },
        headers={
            "Authorization": os.getenv("DRAFTERS_AUTH_TOKEN")
        },
        method="GET",
        is_active=True,
        class_name="Drafters",
        file_name="drafters",
    ),
    DFSProvider(
        title="Boom Fantasy",
        name="boom",
        url={
            "main_url": "https://production-boom-dfs-backend-api.boomfantasy.com/api/v1/contests/multiLine/99708fb7-167a-4314-b69d-e38dc782a63a?questionStatus=available&renderType=multiLine"
        },
        headers={
              'x-app-name': 'Boom',
              'x-app-version': '41',
              'x-product-id': 'boom_dfs',
              'x-app-build': '176',
              'x-device-id': '48e0c8468226f089',
              'x-platform': 'android',
              'access-control-allow-origin': '*',
              'authorization': os.getenv("boom_auth_token"),
              'if-none-match': 'W/"118d-Ko20dOxZMQt3uUUiTsEJZ5sZZDs"'
        },
        method="GET",
        is_active=False,
        class_name="Boom",
        file_name="boom",
    ),
    DFSProvider(
        title="ParlayPlay",
        name="parlayplay",
        url={
            "main_url": "http://45.61.52.251:8000/parlayplay?sport={sport}&league={league}&period={period}",
            "league_url": "http://45.61.52.251:8000/parlayplay/leagues"
        },
        method="GET",
        is_active=False,
        class_name="Parlayplay",
        file_name="parlayplay",
    ),
    DFSProvider(
        title="Splash Sports",
        name="splashsports",
        url={
            "main_url": "https://api.splashsports.com/props-service/api/props?limit=1000&offset=0"
        },
        headers={
            "Authorization": os.getenv("splash_auth_token"),
        },
        method="GET",
        is_active=False,
        class_name="SplashSports",
        file_name="splashsports",
    ),
    DFSProvider(
        title="Parlaye",
        name="parlaye",
        url={
            "main_url": "https://m2efyeevmf.us-east-2.awsapprunner.com/available_picks/get-player-picks/"
        },
        method="POST",
        is_active=False,
        class_name="Parlaye",
        file_name="parlaye",
    ),
    DFSProvider(
        title="DraftKings Pick 6",
        name="draftkings_6",
        url= {
            "league_list_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/main?showLive=false&appname=psxandroid&version=253542100&format=json",
            "league_data_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/identifier?pillIdentifier={sport_key}&appname=psxandroid&version=260861600&format=json",
            "main_market_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/{league_id}/category/pickcards?appname=psxandroid&version=260861600&format=json",
            "individual_market_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/{league_id}/category/pickcards?pickCategoryId={category_id}&appname=psxandroid&version=260861600&format=json"
        },
        method="GET",
        is_active=True,
        class_name="DraftKingsPickSix",
        file_name="draftkings_6",
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
        is_active=True,
        class_name="Sleeper",
        file_name="sleeper",
    ),
    DFSProvider(
        title="Dabble",
        name="dabble",
        url={
            "main_url": "https://api.dabble.com/competitions/active/", # Leagues
            "alternate_url": "https://api.dabble.com/competitions/{league_id}/sport-fixtures?exclude[]=markets&exclude[]=selections&exclude[]=prices", # Game Ids
            "alternate_url_2": "https://api.dabble.com/sportfixtures/details/{game_id}?filter=dfs-enabled",
        },
        headers={
            "x-device-id": "48e0c8468226f089",
            "x-app-version": "4.17.10+019ededb",
            "authorization": "",
        },
        method="GET",
        is_active=True,
        class_name="Dabble",
        file_name="dabble",
    ),
    DFSProvider(
        title="Chalkboard",
        name="chalkboard",
        url={
            "main_url": os.getenv("CHALKBOARD_URL")
        },
        method="POST",
        is_active=False,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="chalkboard_access_token",
            base_file_path=DFSProvider.base_file_path,
            class_name="ChalkboardAuth",
            file_name="chalkboard_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="dfs_chalkboard_auth",
                interval=1620,
                name="DFS Chalkboard Auth",
            )
        ),
        class_name="Chalkboard",
        file_name="chalkboard",
    ),
    DFSProvider(
        title="Epick Fantasy",
        name="epicks",
        url={
            "league_url": "https://sportsdata.prod.epickfantasy.com/api/sports-leagues-mix/ui?state_or_territory=CA&mode=DUEL",
            "main_url": "https://sportsdata.prod.epickfantasy.com/api/projections/ui?state_or_territory=CA&league={league}&mode=DUEL&dependencies=Event%2CPlayer%2CTeam%2CProp",
            "stat_url": "https://sportsdata.prod.epickfantasy.com/api/props/ui?state_or_territory=CA&mode=DUEL&limit=1000"
        },
        method="GET",
        is_active=False,
        class_name="Epicks",
        file_name="epicks",
    )
]