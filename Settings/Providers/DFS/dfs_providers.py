import os
from dotenv import load_dotenv
from Settings.Providers.base_provider import BaseProvider

load_dotenv()


# List of DFS providers with their configurations.
DFS_PROVIDERS = [
    BaseProvider(
        title="Underdog Fantasy",
        name="underdog",
        url={
            "main_url": "https://api.underdogfantasy.com/beta/v6/over_under_lines",
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
        title="PrizePicks",
        name="prizepicks",
        url={
            "main_url": "https://partner-api.prizepicks.com/projections"
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
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
        is_active=True
    ),
    BaseProvider(
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
        is_active=False
    ),
    BaseProvider(
        title="Boom Fantasy",
        name="boom",
        url={
            "main_url": "https://production-boom-dfs-backend-api.boomfantasy.com/api/v1/contests/multiLine/99708fb7-167a-4314-b69d-e38dc782a63a?questionStatus=available&renderType=multiLine"
        },
        headers={
            "Authorization": os.getenv("boom_auth_token"),
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
        title="ParlayPlay",
        name="parlayplay",
        url={
            "main_url": "http://45.61.52.251:8000/parlayplay?sport={sport}&league={league}&period={period}",
            "league_url": "http://45.61.52.251:8000/parlayplay/leagues"
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
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
        is_active=False
    ),
    BaseProvider(
        title="Parlaye",
        name="parlaye",
        url={
            "main_url": "https://m2efyeevmf.us-east-2.awsapprunner.com/available_picks/get-player-picks/"
        },
        method="POST",
        is_active=True
    ),
    BaseProvider(
        title="DraftKings Pick 6",
        name="draftkings_6",
        url= {
            "league_list_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/main?showLive=false&appname=psxandroid&version=253542100&format=json",
            "league_data_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/identifier?pillIdentifier={sport_key}&appname=psxandroid&version=260861600&format=json",
            "main_market_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/{league_id}/category/pickcards?appname=psxandroid&version=260861600&format=json",
            "individual_market_url": "https://api.draftkings.com/sites/US-PSX/pick6/v1/pickgroups/{league_id}/category/pickcards?pickCategoryId={category_id}&appname=psxandroid&version=260861600&format=json"
        },
        headers={
            'accept': 'application/json',
            'user-agent': 'psxandroid/3.0.253542100 null',
            'accept-encoding': 'gzip',
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
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
        is_active=True
    ),
    BaseProvider(
        title="Dabble",
        name="dabble",
        url={
            "main_url": "https://api.dabble.com/competitions/active/", # Leagues
            "alternate_url": "https://api.dabble.com/competitions/{league_id}/sport-fixtures?exclude[]=markets&exclude[]=selections&exclude[]=prices", # Game Ids
            "alternate_url_2": "https://api.dabble.com/sportfixtures/details/{game_id}?filter=dfs-enabled",
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
        title="Chalkboard",
        name="chalkboard",
        url={
            "main_url": os.getenv("CHALKBOARD_URL")
        },
        method="POST",
        is_active=True
    ),
    BaseProvider(
        title="Epick Fantasy",
        name="epicks",
        url={
            "league_url": "https://sportsdata.prod.epickfantasy.com/api/sports-leagues-mix/ui?state_or_territory=CA&mode=DUEL",
            "main_url": "https://sportsdata.prod.epickfantasy.com/api/projections/ui?state_or_territory=CA&league={league}&mode=DUEL&dependencies=Event%2CPlayer%2CTeam%2CProp",
            "stat_url": "https://sportsdata.prod.epickfantasy.com/api/props/ui?state_or_territory=CA&mode=DUEL&limit=1000"
        },
        method="GET",
        is_active=True
    )
]