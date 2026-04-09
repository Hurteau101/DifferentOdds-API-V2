from Settings.Providers.base_provider import BaseProvider

SPORTSBOOKS_PROVIDERS = [
    BaseProvider(
        title="Bet105",
        name="bet105",
        url={
            "sportsbooks": "https://api.kibl.io/sports/get/reference/sportsbooks",
            "leagues": "https://api.kibl.io/sports/get/reference/leagues",
            "segments": "https://api.kibl.io/sports/get/reference/segments",
            "sides": "https://api.kibl.io/sports/get/reference/sides",
            "market_genre": "https://api.kibl.io/sports/get/reference/market-genres",
            "market_status": "https://api.kibl.io/sports/get/reference/market-statuses",
            "market_types": "https://api.kibl.io/sports/get/reference/market-types",
            "fixture_types": "https://api.kibl.io/sports/get/reference/fixture-types",
            "fixtures": "https://api.kibl.io/sports/get/info/fixtures",
            "events": "https://api.kibl.io/sports/get/mapping/fixtures",
            "markets": "https://api.kibl.io/sports/get/info/markets",
        },
        method="GET",
        headers={
            "Accept": "application/json",
        },
        is_active=True
    ),
    BaseProvider(
        title="STS",
        name="sts",
        url={
            "category_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuMainHeaders",
            "league_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuLeaguesWithOpenGames",
            "market_url": "https://bettheguys.com/Player/app/services/linesAJX.aspx/GetLines"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json; charset=utf-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://bettheguys.com',
            'Connection': 'keep-alive',
            'Referer': 'https://bettheguys.com/Player/main.aspx',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers'
        },
        method="POST",
        is_active=True
    ),
    BaseProvider(
        title="Ace",
        name="ace",
        url={
            "leagues_url": "https://backend.betvegas23.com/wager/ActiveLeaguesHelper.aspx?WT=0",
            "market_url": "https://backend.betvegas23.com/wager/NewScheduleHelper.aspx"
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://betvegas23.com/",
            "Origin": "https://betvegas23.com",
        },
        method="POST",
        is_active=False
    ),
    BaseProvider(
        title="1BV",
        name="1bv",
        url={
            "app_token_url": "https://everygame247.com/BetSlip/configurations/systemPreferences/systemKeys.json?version=1775274578684",
            "player_token_url": "https://everygame247.com/Actions/api/Login/PlayerLogin?player={username}&password={password}&domain=https://everygame247.com",
            "leagues_url": "https://everygame247.com/Actions/api/Menu/GetMenu",
            "event_url": "https://everygame247.com/Actions/api/Event/GetEvent"
        },
        headers={
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://everygame247.com',
            'Referer': 'https://everygame247.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        },
        method="GET",
        is_active=True
    ),
    BaseProvider(
        title="Metallic",
        name="metallic",
        url={
            "league_url": "https://black34.com/player-api/api/wager/sportsavailablebyplayeronleague/false",
            "market_url": "https://black34.com/player-api/api/wager/schedules/S/0"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'Origin': 'https://black34.com',
            'Connection': 'keep-alive',
            'Referer': 'https://black34.com/v2/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0',
        },
        method="POST",
        is_active=True
    ),
    BaseProvider(
        title="Buckeye 2",
        name="buckeye2",
        url={
            "league_url": "https://wwcd.me/cloud/api/League/Get_SportsLeagues",
            "market_url": "https://wwcd.me/cloud/api/Lines/Get_LeagueLines2",
            "point_group_url": "https://wwcd.me/cloud/api/Lines/getBuyPointsGroup"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://wwcd.me',
            'Connection': 'keep-alive',
            'Referer': 'https://wwcd.me/sports.html?v=1775430461341',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers'
        },
        method="POST",
        is_active=True
    )
]