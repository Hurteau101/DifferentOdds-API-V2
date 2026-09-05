from dataclasses import dataclass
from Settings.Providers.base_provider import BaseProvider, AuthJobDict, MapperJobDict, RedisSelector, \
    APSchedulerDetails, CeleryDetails


@dataclass
class SportsbooksProvider(BaseProvider):
    base_file_path = "Books.Sportsbooks"
    celery_details: CeleryDetails = CeleryDetails(
        interval=45,
        lock_timeout=180,
        book_type="Sportsbook",
        soft_limit=120,
        hard_limit=160,
    )


SPORTSBOOKS_PROVIDERS = [
    SportsbooksProvider(
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
        is_active=True,
        mapper_job_dict=MapperJobDict(
            job_type=RedisSelector.MAPPER,
            job_active=True,
            requires_auth=True,
            mapper_redis_key="bet105_mapper_data",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="Bet105Mapper",
            file_name="bet105_mapping",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_bet105_mapper",
                interval=72000,
                name="Sportsbook Bet105 Mapper",
            )
        ),
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="bet105_auth_token",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="Bet105Auth",
            file_name="bet105_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_bet105_auth",
                interval=72000,
                name="Sportsbook Bet105 Auth",
            )
        ),
        class_name="Bet105",
        file_name="bet105",
    ),
    SportsbooksProvider(
        title="STS",
        name="sts",
        url={
            "category_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuMainHeaders",
            "league_url": "https://bettheguys.com/Player/app/services/sidebarsportAJX.aspx/GetSportMenuLeaguesWithOpenGames",
            "market_url": "https://bettheguys.com/Player/app/services/linesAJX.aspx/GetLines"
        },
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://bettheguys.com',
            'Connection': 'keep-alive',
            'Referer': 'https://bettheguys.com/Player/main.aspx',
            'TE': 'trailers'
        },
        method="POST",
        is_active=True,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="sts_cookies",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="STSAuth",
            file_name="sts_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_sts_auth",
                interval=900,
                name="Sportsbook STS Auth",
            )

        ),
        class_name="STS",
        file_name="sts",
    ),
    SportsbooksProvider(
        title="Ace",
        name="ace",
        url={
            "leagues_url": "https://backend.betvegas23.com/wager/ActiveLeaguesHelper.aspx?WT=0",
            "market_url": "https://backend.betvegas23.com/wager/NewScheduleHelper.aspx"
        },
        headers={
            "Referer": "https://betvegas23.com/",
            "Origin": "https://betvegas23.com",
        },
        method="POST",
        is_active=True,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="ace_cookies",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="AceAuth",
            file_name="ace_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_ace_auth",
                interval=900,
                name="Sportsbook Ace Auth",
            )
        ),
        class_name="Ace",
        file_name="ace",
        celery_details=CeleryDetails(
            interval=120,
            lock_timeout=240,
            book_type="Sportsbook",
            soft_limit=120,
            hard_limit=160,
        ),
    ),
    SportsbooksProvider(
        title="1BV",
        name="1bv",
        url={
            "app_token_url": "https://everygame247.com/BetSlip/configurations/systemPreferences/systemKeys.json?version=1775274578684",
            "player_token_url": "https://everygame247.com/Actions/api/Login/PlayerLogin?player={username}&password={password}&domain=https://everygame247.com",
            "leagues_url": "https://everygame247.com/Actions/api/Menu/GetMenu",
            "event_url": "https://everygame247.com/Actions/api/Event/GetEvent"
        },
        headers={
            'Origin': 'https://everygame247.com',
            'Referer': 'https://everygame247.com/',
            'Connection': 'keep-alive',
        },
        method="GET",
        is_active=True,
        class_name="OneBv",
        file_name="onebv",
    ),
    SportsbooksProvider(
        title="Metallic",
        name="metallic",
        url={
            "league_url": "https://black34.com/player-api/api/wager/sportsavailablebyplayeronleague/false",
            "market_url": "https://black34.com/player-api/api/wager/schedules/S/0"
        },
        headers={
            'Origin': 'https://black34.com',
            'Connection': 'keep-alive',
            'Referer': 'https://black34.com/v2/',
        },
        method="POST",
        is_active=True,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="metallic_token",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="MetallicAuth",
            file_name="metallic_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_metallic_auth",
                interval=900,
                name="Sportsbook Metallic Auth",
            )
        ),
        class_name="Metallic",
        file_name="metallic",
    ),
    SportsbooksProvider(
        title="Buckeye 2",
        name="buckeye2",
        url={
            # "league_url": "https://wwcd.me/cloud/api/League/Get_SportsLeagues",
            # "market_url": "https://wwcd.me/cloud/api/Lines/Get_LeagueLines2",
            # "point_group_url": "https://wwcd.me/cloud/api/Lines/getBuyPointsGroup"
            "league_url": "https://www.247bettor.com/cloud/api/League/Get_SportsLeagues",
            "market_url": "https://www.247bettor.com/cloud/api/Lines/Get_LeagueLines2",
            "point_group_url": "https://www.247bettor.com/cloud/api/Lines/getBuyPointsGroup"
        },
        headers={
            # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:149.0) Gecko/20100101 Firefox/149.0',
            # 'Accept': '*/*',
            # 'Accept-Encoding': 'gzip, deflate',
            # 'Accept-Language': 'en-US,en;q=0.9',
            # 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            # 'Origin': 'https://wwcd.me',
            'Origin': 'https://www.247bettor.com',
            'Connection': 'keep-alive',
            # 'Referer': 'https://wwcd.me/sports.html?v=1775430461341',
            'Referer': 'https://www.247bettor.com/',
            # 'Sec-Fetch-Dest': 'empty',
            # 'Sec-Fetch-Mode': 'cors',
            # 'Sec-Fetch-Site': 'same-origin',
            'TE': 'trailers'
        },
        method="POST",
        is_active=True,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=True,
            auth_redis_key="buckeye_2_auth_token",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="Buckeye2Auth",
            file_name="buckeye2_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_buckeye_2_auth",
                interval=900,
                name="Sportsbook Buckeye2 Auth",
            )
        ),
        class_name="Buckeye2",
        file_name="buckeye_2",
    ),
    SportsbooksProvider(
        title="Buckeye 1",
        name="buckeye1",
        url={
            "market_url": "https://playnow365.com/Qubic/PlayerGameSelection.php"
        },
        headers={
            'Connection': 'keep-alive',
            'Host': 'playnow365.com',
            'Origin': 'https://playnow365.com',
            'Referer': 'https://playnow365.com/Qubic/StraightSportSelection.php',
        },
        method="POST",
        is_active=False,
        auth_job_dict=AuthJobDict(
            job_type=RedisSelector.AUTH,
            job_active=False,
            auth_redis_key="buckeye1_cookies",
            base_file_path=SportsbooksProvider.base_file_path,
            class_name="Buckeye1Auth",
            file_name="buckeye1_auth",
            ap_scheduler=APSchedulerDetails(
                job_id="sportsbook_buckeye_1_auth",
                interval=900,
                name="Sportsbook Buckeye1 Auth",
            )
        ),
        class_name="Buckeye1",
        file_name="buckeye_1",
        ),
        # BaseProvider(
        #     title="Prop Builder",
        #     name="prop_builder",
        #     url={
        #         "league_url": "https://bv2-us.digitalsportstech.com/api/sgmLeagues?sb=betus&user=undefined&legacy=1",
        #         "game_url": "https://bv2-us.digitalsportstech.com/api/sgmGames?sb=betus",
        #         "market_url": "https://bv2-us.digitalsportstech.com/api/grouped-markets/v2/map?sb=betus&legacy=1",
        #         "props_base": "https://bv2-us.digitalsportstech.com/api/",
        #     },
        #     headers={
        #         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0',
        #         'Accept': 'application/json, text/plain, */*',
        #         'Accept-Language': 'en-US,en;q=0.9',
        #         'Accept-Encoding': 'gzip, deflate, zstd',
        #         'Origin': 'https://troya.xyz',
        #         'Connection': 'keep-alive',
        #         'Referer': 'https://troya.xyz/',
        #         'Sec-Fetch-Dest': 'empty',
        #         'Sec-Fetch-Mode': 'cors',
        #         'Sec-Fetch-Site': 'cross-site'
        #     },
        #     method="GET",
        #     is_active=True
        # )
]