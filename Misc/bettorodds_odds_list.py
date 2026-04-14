### In charge of creating sets of different names of stats, teams, etc ####
from Cron_Jobs.bettorodds_odds import load_bettorodds
from Redis.redis_manager import RedisSyncManager

import json

RETRY = 0

def run(matches: bool, player: bool, stat_type: bool, leagues: bool, save_json: bool = True):
    global RETRY
    redis_instance = RedisSyncManager(database=8)
    bettorodds_data = redis_instance.get_data("bettoroddds_odds")

    if RETRY > 1:
        raise Exception("Exceeded maximum retry attempts to load BettorOdds data from Redis.")

    if not bettorodds_data:
        bettorodds_data = load_bettorodds()
        run(matches, player, stat_type, leagues, save_json)
        RETRY += 1

    set_data = {
        "matches": set(),
        "players": {},
        "stat_types": {},
        "leagues": set(),
    }


    for odds in bettorodds_data.values():
        league = odds.get("League", "")

        if matches:
            set_data["matches"].add(odds.get("Match", ""))

        if player:
            set_data["players"].setdefault(league, {}).setdefault(odds.get("Player", ""), set())

        if stat_type:
            set_data["stat_types"].setdefault(league, set()).add(odds.get("Prop", ""))

        if leagues:
            set_data["leagues"].add(league)

    with open("bettorodds_sets.json", "w") as f:
        json.dump(
            {
                key: (
                    {k: list(v) for k, v in value.items()}
                    if isinstance(value, dict)
                    else list(value)
                )
                for key, value in set_data.items()
            },
            f,
            indent=2
        )
    return set_data




if __name__ == "__main__":
    run(matches=False, player=False, stat_type=True, leagues=False)

