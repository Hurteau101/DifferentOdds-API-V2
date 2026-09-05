import asyncio

from Redis.redis_manager import static_mapping_service
from External_Book_Mapping.base_mapper import BaseMapper
from Monitoring.monitoring import create_sentry_message
from Redis.redis_manager import RedisAsyncManager
from Utils.request_caller import SportbookRequestType
from curl_cffi import AsyncSession

### MOVE GET STATIC METHOD TO BASE CLASS AFTER TESTING FURTHER
ADDITIONAL_MARKET_MAPPING = {
    "NHL": {
        "spread": "Puck Line"
    }
}

class StakeMapping(BaseMapper):
    # ALLOWED_LEAGUES = ["ice-hockey", "basketball"]
    ALLOWED_LEAGUES = ["ice-hockey"]
    def __init__(self):
        super().__init__(book_name="stake", category="sgp", request_type=SportbookRequestType.SPOOF)

    # async def _get_main_markets(self, main_markets: list, selection_name):
    #     main = {}
    #
    #     for main in main_markets:





    async def _direction_mapper(self, length_of_bets: int):
        if length_of_bets == 1:
            return "over"

        return None


    async def _map_data(self, session: AsyncSession, event_ids: list):
        event_ids = ["46314420-detroit-red-wings-florida-panthers"]
        async def process_mapping(event_id, semaphore: asyncio.Semaphore):
            async with semaphore:
                results = await self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("general_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "query": "query SwishMarket_SlugFixture($fixture: String!, $atBat: Boolean! = false, $inPlay: Boolean!) {\n  slugFixture(fixture: $fixture) {\n    ...TeamMarket_SportFixture\n    data {\n      __typename\n      ... on SportFixtureDataMatch {\n        competitors {\n          extId\n        }\n      }\n    }\n    swishGame {\n      id\n      status\n    }\n    swishGameTeams {\n      id\n      name\n      markets {\n        trading {\n          betFactor\n        }\n        stat {\n          type\n        }\n        ...TeamMarket_SwishMarket\n        ...SwishTemplateWinner_SwishMarket\n        ...SwishTemplateHandicap_SwishMarket\n      }\n      players {\n        id\n        ...TeamMarket_SwishCompetitor\n        ...SwishMarketTeam_SwishCompetitor\n        markets(inPlay: $inPlay, statTypes: [match, player, match_props, team_props]) {\n          ...TeamMarket_SwishMarket\n          ...SwishTemplateWinner_SwishMarket\n          ...SwishTemplateHandicap_SwishMarket\n        }\n      }\n    }\n  }\n}\n\nfragment TeamMarket_SportFixture on SportFixture {\n  ...CustomSwishBetOutcome_SportFixture\n  ...SwishBetOutcome_SportFixture\n  swishGame {\n    status\n    swishSportId\n  }\n}\n\nfragment CustomSwishBetOutcome_SportFixture on SportFixture {\n  id\n  status\n  tournament {\n    slug\n  }\n  data {\n    ... on SportFixtureDataMatch {\n      competitors {\n        name\n        abbreviation\n      }\n      startTime\n    }\n    ... on SportFixtureDataOutright {\n      name\n      startTime\n    }\n  }\n}\n\nfragment SwishBetOutcome_SportFixture on SportFixture {\n  id\n  status\n  tournament {\n    slug\n  }\n  data {\n    ... on SportFixtureDataMatch {\n      competitors {\n        name\n        abbreviation\n      }\n      startTime\n    }\n    ... on SportFixtureDataOutright {\n      name\n      startTime\n    }\n  }\n}\n\nfragment TeamMarket_SwishMarket on SwishMarket {\n  ...CustomSwishBetOutcome_SwishMarket\n  ...SwishBetOutcome_SwishMarket\n  stat {\n    name\n    value\n  }\n  lines {\n    ...CustomSwishBetOutcome_SwishMarketOutcome\n    ...SwishBetOutcome_SwishMarketOutcome\n    id\n    balanced\n    over\n    under\n    line\n  }\n}\n\nfragment CustomSwishBetOutcome_SwishMarket on SwishMarket {\n  id\n  stat {\n    swishStatId\n    name\n    value\n    customBet\n    liveCustomBetAvailable\n    type\n  }\n}\n\nfragment SwishBetOutcome_SwishMarket on SwishMarket {\n  id\n  stat {\n    swishStatId\n    name\n    value\n  }\n  data @include(if: $atBat) {\n    atBat {\n      marketDurationStart\n      half\n      inning\n      pitcherName\n    }\n  }\n}\n\nfragment CustomSwishBetOutcome_SwishMarketOutcome on SwishMarketOutcome {\n  id\n  line\n  over\n  under\n  push\n  suspended\n  balanced\n}\n\nfragment SwishBetOutcome_SwishMarketOutcome on SwishMarketOutcome {\n  id\n  line\n  over\n  under\n  push\n  suspended\n  balanced\n}\n\nfragment SwishTemplateWinner_SwishMarket on SwishMarket {\n  ...CustomSwishBetOutcome_SwishMarket\n  lines {\n    ...CustomSwishBetOutcome_SwishMarketOutcome\n  }\n  competitor {\n    name\n  }\n}\n\nfragment SwishTemplateHandicap_SwishMarket on SwishMarket {\n  ...CustomSwishBetOutcome_SwishMarket\n  lines {\n    ...CustomSwishBetOutcome_SwishMarketOutcome\n  }\n  competitor {\n    name\n  }\n}\n\nfragment TeamMarket_SwishCompetitor on SwishCompetitor {\n  id\n  ...CustomSwishBetOutcome_SwishCompetitor\n  ...SwishBetOutcome_SwishCompetitor\n}\n\nfragment CustomSwishBetOutcome_SwishCompetitor on SwishCompetitor {\n  name\n}\n\nfragment SwishBetOutcome_SwishCompetitor on SwishCompetitor {\n  name\n}\n\nfragment SwishMarketTeam_SwishCompetitor on SwishCompetitor {\n  id\n  name\n  position\n  ...TeamMarket_SwishCompetitor\n  markets(inPlay: $inPlay, statTypes: [match, player, match_props, team_props]) {\n    ...TeamMarket_SwishMarket\n    id\n    trading {\n      betFactor\n    }\n    stat {\n      customBet\n      liveCustomBetAvailable\n    }\n  }\n}",
                        "variables": {
                            "fixture": event_id,
                            "inPlay": False
                        }
                    }
                )

                return event_id, (results if results else {})

        semaphore = asyncio.Semaphore(20)
        tasks = [process_mapping(event_id, semaphore) for event_id in event_ids]
        results = await asyncio.gather(*tasks)

        mapping_data = {}
        import json

        for event_id, result in results:
            league = result.get("data", {}).get("slugFixture",{}).get("tournament", {}).get("slug")
            event_bucket = {}
            data_result = result.get("data", {}).get("slugFixture", {}).get("swishGameTeams", [])
            if not data_result:
                continue

            for game in data_result:
                main_selection_name = game.get("name")
                main_market_bucket = {}

                for main_market in game.get("markets", []):
                    raw_market_name = main_market.get("stat", {}).get("name")
                    market_name = ADDITIONAL_MARKET_MAPPING.get(league.upper(), {}).get(raw_market_name, raw_market_name)

                    market_bucket = main_market_bucket.setdefault(market_name, {})

                    length_of_lines = len(main_market.get("lines", []))

                    for index, market in enumerate(main_market.get("lines", [])):
                        line = market.get("line", 0)
                        direction = await self._direction_mapper(length_of_lines)

                        if line:
                            pass


                        selection_bucket = market_bucket.setdefault(main_selection_name, {})
                        selection_bucket.update({
                            "outcome_id": market.get("id"),
                            "direction": direction,
                        })

                print(json.dumps(main_market_bucket, indent=2))
                # main_markets = {
                #     market.get("stat", {}).get("name"): None
                #     for market in game.get("markets", [])
                #     for line in market.get("lines", [])
                # }




            # This is moneyline section
            # main_market = result.get()


    async def run_scheduler(self, session: AsyncSession, redis_instance: RedisAsyncManager):
        raw_event_data = await asyncio.gather(
            *[
                self.api_caller(
                    book_name=self.book_data.name,
                    session=session,
                    url=self.book_data.mapping.url.get("general_url"),
                    method=self.book_data.mapping.method,
                    headers=self.book_data.mapping.headers,
                    parse_json=True,
                    payload={
                        "query": "query SportIndex($sport: String!, $group: String!, $type: SportSearchEnum = popular) {\n  slugSport(sport: $sport) {\n    id\n    name\n    templates(group: $group) {\n      id\n      name\n      extId\n    }\n    firstTournament: tournamentList(type: $type, limit: 1) {\n      id\n      name\n      slug\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n      fixtureCount(type: $type)\n      fixtureList(type: $type, limit: 10) {\n        ...FixturePreview\n        ...UfcFrontRowSeat\n        groups(groups: [$group], status: [active, suspended, deactivated]) {\n          ...SportGroupTemplates\n        }\n      }\n    }\n    tournamentList(type: $type, limit: 5) {\n      id\n      name\n      slug\n      fixtureCount(type: $type)\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n    }\n    categoryList(type: $type, limit: 100) {\n      id\n      slug\n      name\n      countryCode\n      fixtureCount(type: $type)\n      tournamentList(type: $type, limit: 100) {\n        id\n        slug\n        name\n        fixtureCount(type: $type)\n        category {\n          id\n          slug\n          name\n          countryCode\n        }\n      }\n    }\n  }\n}\n\nfragment FixturePreview on SportFixture {\n  id\n  ...SportFixtureLiveStreamExists\n  ...FixtureOptionsSameGameMultiButton_SportFixture\n  status\n  slug\n  name\n  provider\n  marketCount(status: [active, suspended])\n  extId\n  liveWidgetUrl\n  widgetUrl\n  data {\n    __typename\n    ...SportFixtureDataMatch\n    ...SportFixtureDataOutright\n  }\n  tournament {\n    ...TournamentTreeNested\n  }\n  eventStatus {\n    ...SportFixtureEventStatus\n    ...EsportFixtureEventStatus\n  }\n}\n\nfragment SportFixtureLiveStreamExists on SportFixture {\n  id\n  betradarStream {\n    exists\n  }\n  imgArenaStream {\n    exists\n  }\n  abiosStream {\n    exists\n    stream {\n      startTime\n      id\n    }\n  }\n  geniussportsStream(deliveryType: hls) {\n    exists\n  }\n  statsPerformStream(getData: false) {\n    isAvailable\n    geoBlocked\n  }\n}\n\nfragment FixtureOptionsSameGameMultiButton_SportFixture on SportFixture {\n  sgmAvailable: customBetAvailable\n  swish: swishGame {\n    sport: swishSport {\n      sgmAvailable: customBetAvailable\n      sgmLiveAvailable: liveCustomBetAvailable\n    }\n  }\n}\n\nfragment SportFixtureDataMatch on SportFixtureDataMatch {\n  startTime\n  competitors {\n    ...SportFixtureCompetitor\n  }\n  teams {\n    name\n    qualifier\n  }\n  tvChannels {\n    language\n    name\n    streamUrl\n  }\n  __typename\n}\n\nfragment SportFixtureCompetitor on SportFixtureCompetitor {\n  name\n  defaultName\n  extId\n  countryCode\n  abbreviation\n  iconPath\n}\n\nfragment SportFixtureDataOutright on SportFixtureDataOutright {\n  name\n  startTime\n  endTime\n  __typename\n}\n\nfragment TournamentTreeNested on SportTournament {\n  id\n  name\n  slug\n  category {\n    ...CategoryTreeNested\n    cashoutEnabled\n  }\n}\n\nfragment CategoryTreeNested on SportCategory {\n  id\n  name\n  slug\n  sport {\n    id\n    name\n    slug\n  }\n}\n\nfragment SportFixtureEventStatus on SportFixtureEventStatusData {\n  __typename\n  homeScore\n  awayScore\n  matchStatus\n  clock {\n    matchTime\n    remainingTime\n  }\n  periodScores {\n    homeScore\n    awayScore\n    matchStatus\n  }\n  currentTeamServing\n  homeGameScore\n  awayGameScore\n  statistic {\n    yellowCards {\n      away\n      home\n    }\n    redCards {\n      away\n      home\n    }\n    corners {\n      home\n      away\n    }\n  }\n}\n\nfragment EsportFixtureEventStatus on EsportFixtureEventStatus {\n  matchStatus\n  homeScore\n  awayScore\n  scoreboard {\n    homeGold\n    awayGold\n    homeGoals\n    awayGoals\n    homeKills\n    awayKills\n    gameTime\n    homeDestroyedTowers\n    awayDestroyedTurrets\n    currentRound\n    currentCtTeam\n    currentDefTeam\n    time\n    awayWonRounds\n    homeWonRounds\n    remainingGameTime\n  }\n  periodScores {\n    type\n    number\n    awayGoals\n    awayKills\n    awayScore\n    homeGoals\n    homeKills\n    homeScore\n    awayWonRounds\n    homeWonRounds\n    matchStatus\n  }\n  __typename\n}\n\nfragment UfcFrontRowSeat on SportFixture {\n  frontRowSeatFight {\n    fightId\n  }\n  tournament {\n    frontRowSeatEvent {\n      identifier\n    }\n  }\n}\n\nfragment SportGroupTemplates on SportGroup {\n  ...SportGroup\n  templates(limit: 10, includeEmpty: true) {\n    ...SportGroupTemplate\n    markets(limit: 1) {\n      ...SportMarket\n      outcomes {\n        ...SportMarketOutcome\n      }\n    }\n  }\n}\n\nfragment SportGroup on SportGroup {\n  name\n  translation\n  rank\n}\n\nfragment SportGroupTemplate on SportGroupTemplate {\n  extId\n  rank\n  name\n}\n\nfragment SportMarket on SportMarket {\n  id\n  name\n  status\n  extId\n  specifiers\n  customBetAvailable\n  provider\n}\n\nfragment SportMarketOutcome on SportMarketOutcome {\n  __typename\n  id\n  active\n  odds\n  name\n  customBetAvailable\n}",
                        "variables": {
                            "sport": sport_id,
                            "group": "winner"
                        }
                    }
                )
                for sport_id in StakeMapping.ALLOWED_LEAGUES
            ]
        )

        event_ids = [
            slug
            for data in raw_event_data
            if data
            for event_data in data.get("data", {}).get("slugSport", {}).get("firstTournament", [])
            for fixture in event_data.get("fixtureList", [])
            if (slug := fixture.get("slug"))
        ]

        print(event_ids)

        await self._map_data(session=session, event_ids=event_ids)





if __name__ == "__main__":
    redis_instance = RedisAsyncManager(database=2)
    mapper = StakeMapping()
    async def main():
        async with AsyncSession(impersonate="chrome120") as session:
            await mapper.run_scheduler(session=session, redis_instance=redis_instance)
    asyncio.run(main())












#
#
# import json
#
#
#
# payload = json.dumps({
#   "query": "query SportIndex($sport: String!, $group: String!, $type: SportSearchEnum = popular) {\n  slugSport(sport: $sport) {\n    id\n    name\n    templates(group: $group) {\n      id\n      name\n      extId\n    }\n    firstTournament: tournamentList(type: $type, limit: 1) {\n      id\n      name\n      slug\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n      fixtureCount(type: $type)\n      fixtureList(type: $type, limit: 10) {\n        ...FixturePreview\n        ...UfcFrontRowSeat\n        groups(groups: [$group], status: [active, suspended, deactivated]) {\n          ...SportGroupTemplates\n        }\n      }\n    }\n    tournamentList(type: $type, limit: 5) {\n      id\n      name\n      slug\n      fixtureCount(type: $type)\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n    }\n    categoryList(type: $type, limit: 100) {\n      id\n      slug\n      name\n      countryCode\n      fixtureCount(type: $type)\n      tournamentList(type: $type, limit: 100) {\n        id\n        slug\n        name\n        fixtureCount(type: $type)\n        category {\n          id\n          slug\n          name\n          countryCode\n        }\n      }\n    }\n  }\n}\n\nfragment FixturePreview on SportFixture {\n  id\n  ...SportFixtureLiveStreamExists\n  ...FixtureOptionsSameGameMultiButton_SportFixture\n  status\n  slug\n  name\n  provider\n  marketCount(status: [active, suspended])\n  extId\n  liveWidgetUrl\n  widgetUrl\n  data {\n    __typename\n    ...SportFixtureDataMatch\n    ...SportFixtureDataOutright\n  }\n  tournament {\n    ...TournamentTreeNested\n  }\n  eventStatus {\n    ...SportFixtureEventStatus\n    ...EsportFixtureEventStatus\n  }\n}\n\nfragment SportFixtureLiveStreamExists on SportFixture {\n  id\n  betradarStream {\n    exists\n  }\n  imgArenaStream {\n    exists\n  }\n  abiosStream {\n    exists\n    stream {\n      startTime\n      id\n    }\n  }\n  geniussportsStream(deliveryType: hls) {\n    exists\n  }\n  statsPerformStream(getData: false) {\n    isAvailable\n    geoBlocked\n  }\n}\n\nfragment FixtureOptionsSameGameMultiButton_SportFixture on SportFixture {\n  sgmAvailable: customBetAvailable\n  swish: swishGame {\n    sport: swishSport {\n      sgmAvailable: customBetAvailable\n      sgmLiveAvailable: liveCustomBetAvailable\n    }\n  }\n}\n\nfragment SportFixtureDataMatch on SportFixtureDataMatch {\n  startTime\n  competitors {\n    ...SportFixtureCompetitor\n  }\n  teams {\n    name\n    qualifier\n  }\n  tvChannels {\n    language\n    name\n    streamUrl\n  }\n  __typename\n}\n\nfragment SportFixtureCompetitor on SportFixtureCompetitor {\n  name\n  defaultName\n  extId\n  countryCode\n  abbreviation\n  iconPath\n}\n\nfragment SportFixtureDataOutright on SportFixtureDataOutright {\n  name\n  startTime\n  endTime\n  __typename\n}\n\nfragment TournamentTreeNested on SportTournament {\n  id\n  name\n  slug\n  category {\n    ...CategoryTreeNested\n    cashoutEnabled\n  }\n}\n\nfragment CategoryTreeNested on SportCategory {\n  id\n  name\n  slug\n  sport {\n    id\n    name\n    slug\n  }\n}\n\nfragment SportFixtureEventStatus on SportFixtureEventStatusData {\n  __typename\n  homeScore\n  awayScore\n  matchStatus\n  clock {\n    matchTime\n    remainingTime\n  }\n  periodScores {\n    homeScore\n    awayScore\n    matchStatus\n  }\n  currentTeamServing\n  homeGameScore\n  awayGameScore\n  statistic {\n    yellowCards {\n      away\n      home\n    }\n    redCards {\n      away\n      home\n    }\n    corners {\n      home\n      away\n    }\n  }\n}\n\nfragment EsportFixtureEventStatus on EsportFixtureEventStatus {\n  matchStatus\n  homeScore\n  awayScore\n  scoreboard {\n    homeGold\n    awayGold\n    homeGoals\n    awayGoals\n    homeKills\n    awayKills\n    gameTime\n    homeDestroyedTowers\n    awayDestroyedTurrets\n    currentRound\n    currentCtTeam\n    currentDefTeam\n    time\n    awayWonRounds\n    homeWonRounds\n    remainingGameTime\n  }\n  periodScores {\n    type\n    number\n    awayGoals\n    awayKills\n    awayScore\n    homeGoals\n    homeKills\n    homeScore\n    awayWonRounds\n    homeWonRounds\n    matchStatus\n  }\n  __typename\n}\n\nfragment UfcFrontRowSeat on SportFixture {\n  frontRowSeatFight {\n    fightId\n  }\n  tournament {\n    frontRowSeatEvent {\n      identifier\n    }\n  }\n}\n\nfragment SportGroupTemplates on SportGroup {\n  ...SportGroup\n  templates(limit: 10, includeEmpty: true) {\n    ...SportGroupTemplate\n    markets(limit: 1) {\n      ...SportMarket\n      outcomes {\n        ...SportMarketOutcome\n      }\n    }\n  }\n}\n\nfragment SportGroup on SportGroup {\n  name\n  translation\n  rank\n}\n\nfragment SportGroupTemplate on SportGroupTemplate {\n  extId\n  rank\n  name\n}\n\nfragment SportMarket on SportMarket {\n  id\n  name\n  status\n  extId\n  specifiers\n  customBetAvailable\n  provider\n}\n\nfragment SportMarketOutcome on SportMarketOutcome {\n  __typename\n  id\n  active\n  odds\n  name\n  customBetAvailable\n}",
#   "variables": {
#     "sport": "ice-hockey",
#     "group": "winner"
#   }
# })
# headers = {
#   'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
#   'Accept': '*/*',
#   'Accept-Language': 'en-US,en;q=0.9',
#   'Accept-Encoding': 'gzip',
#   'Referer': 'https://stake.com/sports/home',
#   'access-control-allow-origin': '*',
#   'content-type': 'application/json',
#   'x-language': 'en',
#   'x-operation-name': 'SportIndex',
#   'x-operation-type': 'query',
#   'Origin': 'https://stake.com',
#   'Connection': 'keep-alive',
#   'Sec-Fetch-Dest': 'empty',
#   'Sec-Fetch-Mode': 'cors',
#   'Sec-Fetch-Site': 'same-origin',
#   'Priority': 'u=4',
#   'TE': 'trailers',
# }
#
#
#
# from curl_cffi import requests, AsyncSession
#
# url = "https://stake.com/_api/graphql"
#
# response = requests.post(
#     url,
#     impersonate="chrome120",
#     headers=headers,
#     json={
#         "query": "query SportIndex($sport: String!, $group: String!, $type: SportSearchEnum = popular) {\n  slugSport(sport: $sport) {\n    id\n    name\n    templates(group: $group) {\n      id\n      name\n      extId\n    }\n    firstTournament: tournamentList(type: $type, limit: 1) {\n      id\n      name\n      slug\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n      fixtureCount(type: $type)\n      fixtureList(type: $type, limit: 10) {\n        ...FixturePreview\n        ...UfcFrontRowSeat\n        groups(groups: [$group], status: [active, suspended, deactivated]) {\n          ...SportGroupTemplates\n        }\n      }\n    }\n    tournamentList(type: $type, limit: 5) {\n      id\n      name\n      slug\n      fixtureCount(type: $type)\n      category {\n        id\n        slug\n        name\n        countryCode\n      }\n    }\n    categoryList(type: $type, limit: 100) {\n      id\n      slug\n      name\n      countryCode\n      fixtureCount(type: $type)\n      tournamentList(type: $type, limit: 100) {\n        id\n        slug\n        name\n        fixtureCount(type: $type)\n        category {\n          id\n          slug\n          name\n          countryCode\n        }\n      }\n    }\n  }\n}\n\nfragment FixturePreview on SportFixture {\n  id\n  ...SportFixtureLiveStreamExists\n  ...FixtureOptionsSameGameMultiButton_SportFixture\n  status\n  slug\n  name\n  provider\n  marketCount(status: [active, suspended])\n  extId\n  liveWidgetUrl\n  widgetUrl\n  data {\n    __typename\n    ...SportFixtureDataMatch\n    ...SportFixtureDataOutright\n  }\n  tournament {\n    ...TournamentTreeNested\n  }\n  eventStatus {\n    ...SportFixtureEventStatus\n    ...EsportFixtureEventStatus\n  }\n}\n\nfragment SportFixtureLiveStreamExists on SportFixture {\n  id\n  betradarStream {\n    exists\n  }\n  imgArenaStream {\n    exists\n  }\n  abiosStream {\n    exists\n    stream {\n      startTime\n      id\n    }\n  }\n  geniussportsStream(deliveryType: hls) {\n    exists\n  }\n  statsPerformStream(getData: false) {\n    isAvailable\n    geoBlocked\n  }\n}\n\nfragment FixtureOptionsSameGameMultiButton_SportFixture on SportFixture {\n  sgmAvailable: customBetAvailable\n  swish: swishGame {\n    sport: swishSport {\n      sgmAvailable: customBetAvailable\n      sgmLiveAvailable: liveCustomBetAvailable\n    }\n  }\n}\n\nfragment SportFixtureDataMatch on SportFixtureDataMatch {\n  startTime\n  competitors {\n    ...SportFixtureCompetitor\n  }\n  teams {\n    name\n    qualifier\n  }\n  tvChannels {\n    language\n    name\n    streamUrl\n  }\n  __typename\n}\n\nfragment SportFixtureCompetitor on SportFixtureCompetitor {\n  name\n  defaultName\n  extId\n  countryCode\n  abbreviation\n  iconPath\n}\n\nfragment SportFixtureDataOutright on SportFixtureDataOutright {\n  name\n  startTime\n  endTime\n  __typename\n}\n\nfragment TournamentTreeNested on SportTournament {\n  id\n  name\n  slug\n  category {\n    ...CategoryTreeNested\n    cashoutEnabled\n  }\n}\n\nfragment CategoryTreeNested on SportCategory {\n  id\n  name\n  slug\n  sport {\n    id\n    name\n    slug\n  }\n}\n\nfragment SportFixtureEventStatus on SportFixtureEventStatusData {\n  __typename\n  homeScore\n  awayScore\n  matchStatus\n  clock {\n    matchTime\n    remainingTime\n  }\n  periodScores {\n    homeScore\n    awayScore\n    matchStatus\n  }\n  currentTeamServing\n  homeGameScore\n  awayGameScore\n  statistic {\n    yellowCards {\n      away\n      home\n    }\n    redCards {\n      away\n      home\n    }\n    corners {\n      home\n      away\n    }\n  }\n}\n\nfragment EsportFixtureEventStatus on EsportFixtureEventStatus {\n  matchStatus\n  homeScore\n  awayScore\n  scoreboard {\n    homeGold\n    awayGold\n    homeGoals\n    awayGoals\n    homeKills\n    awayKills\n    gameTime\n    homeDestroyedTowers\n    awayDestroyedTurrets\n    currentRound\n    currentCtTeam\n    currentDefTeam\n    time\n    awayWonRounds\n    homeWonRounds\n    remainingGameTime\n  }\n  periodScores {\n    type\n    number\n    awayGoals\n    awayKills\n    awayScore\n    homeGoals\n    homeKills\n    homeScore\n    awayWonRounds\n    homeWonRounds\n    matchStatus\n  }\n  __typename\n}\n\nfragment UfcFrontRowSeat on SportFixture {\n  frontRowSeatFight {\n    fightId\n  }\n  tournament {\n    frontRowSeatEvent {\n      identifier\n    }\n  }\n}\n\nfragment SportGroupTemplates on SportGroup {\n  ...SportGroup\n  templates(limit: 10, includeEmpty: true) {\n    ...SportGroupTemplate\n    markets(limit: 1) {\n      ...SportMarket\n      outcomes {\n        ...SportMarketOutcome\n      }\n    }\n  }\n}\n\nfragment SportGroup on SportGroup {\n  name\n  translation\n  rank\n}\n\nfragment SportGroupTemplate on SportGroupTemplate {\n  extId\n  rank\n  name\n}\n\nfragment SportMarket on SportMarket {\n  id\n  name\n  status\n  extId\n  specifiers\n  customBetAvailable\n  provider\n}\n\nfragment SportMarketOutcome on SportMarketOutcome {\n  __typename\n  id\n  active\n  odds\n  name\n  customBetAvailable\n}",
#         "variables": {
#             "sport": "ice-hockey",
#             "group": "winner"
#         }
#     }
# )
#
# print(response.text)