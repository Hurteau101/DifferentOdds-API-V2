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
            'accept': 'application/json, text/plain, */*',
              'x-app-name': 'Boom',
              'x-app-version': '41',
              'x-product-id': 'boom_dfs',
              'x-app-build': '176',
              'x-device-id': '48e0c8468226f089',
              'x-platform': 'android',
              'access-control-allow-origin': '*',
              'authorization': os.getenv("boom_auth_token"),
              'user-agent': 'okhttp/4.12.0',
              'if-none-match': 'W/"118d-Ko20dOxZMQt3uUUiTsEJZ5sZZDs"'
        },
        method="GET",
        is_active=False
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
        title="Ownerbox",
        name="ownerbox",
        url={
            "stat_url": "https://app.ownersbox.com/fsp/marketType/active?sport={league}",
            "game_url": "https://app.ownersbox.com/fsp/v4/market?sport={league}&marketTypeId={market_id}"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            # 'Accept-Encoding': 'gzip, deflate, br, zstd',
            'OwnersBox-Client-Type': 'web',
            'OwnersBox-Client-Version': '1.11.4',
            'Connection': 'keep-alive',
            'Referer': 'https://app.ownersbox.com/wfs/player-picks/lobby/MLB',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers',
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
        title="FanDuel Picks",
        name="fanduel_picks",
        url={
            "main_url": "https://picks.fanduel.com/lobby.data?sport={league}&_routes=routes%2Flobby%2B%2F_route",
            "stat_url": "https://picks.fanduel.com/api/game-group-props?gameGroupId={game_id}&marketIds=&_data=routes%2Fapi%2B%2Fgame-group-props%2B%2F_resource",
            "multi": "https://picks.fanduel.com/api/bonus-multiplier"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Galaxy S9 Build/TQ2B.230505.005.A1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/101.0.4951.61 Mobile Safari/537.36 CoreWebView-Android/3.0.3 AppInfo (appDomain/picks; region/nj; version/0.0.1; platform/android)',
            'Accept': '*/*',
            'X-Requested-With': 'com.fanduel.flywheelnativecontainer.picks',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://picks.fanduel.com/lobby?sport=NFL&gameGroup=019bd787-377b-7622-a5aa-0dbd7d67454c&stat=Rush+%2B+Rec+TDs',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        method="GET",
        is_active=False
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