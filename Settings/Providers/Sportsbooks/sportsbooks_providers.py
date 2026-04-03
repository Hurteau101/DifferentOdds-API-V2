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
            # "login_url": "https://bettheguys.com/Login.aspx",
            "login_url": "https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx",
            # "league_list_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuMainHeaders",
            "league_list_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuLeaguesWithOpenGames",
            "league_section": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuLeaguesWithOpenGames",
            "game_markets": "https://bettheguys.com/Player/app/services/linesAJX.aspx/GetLines"
        },
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://bettheguys.com',
            'Connection': 'keep-alive',
            'Referer': 'https://bettheguys.com/Logins/001/sites/bettheguys/index.aspx',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Priority': 'u=0, i',
            'TE': 'trailers'
        },
        method="POST",
        is_active=False
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
        is_active=True
    )
]