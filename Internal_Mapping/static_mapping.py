from enum import Enum

from Redis.redis_manager import static_mapping_service
from Utils.helpers import clean_structure, ordinal_formatter


class Category(Enum):
    TEAMS = "teams"
    LEAGUES = "leagues"
    STATS = "stats"

class StaticMapping:
    def __init__(self):
        self.mapping = static_mapping_service.get()

        self.unmapped = {
            "teams": set(),
            "leagues": set(),
            "stats": set(),
        }

    def _look_up(self, bucket: dict, name: str | None, category: Category, league: str | None = None) -> str | dict | None:
        if not name or not bucket:
            return name

        cleaned_name = clean_structure(name)
        raw_name = ordinal_formatter(cleaned_name).lower()

        mapped = bucket.get(raw_name, {})

        if not mapped:
            self.unmapped[category.value].add(f"{league.upper()}|{raw_name}" if league else raw_name)
            return name

        return mapped

    def stat_look_up(self, name: str, remove_player_prefix: bool = True):
        return self._look_up(self.mapping.get("static_mapping", {}), name=name, category=Category.STATS)

    def team_look_up(self, name: str, league: str):
        if not league:
            return name

        return self._look_up(self.mapping.get("team_mapping", {}), name=name, category=Category.TEAMS, league=league)

    def league_look_up(self, name: str):
        return self._look_up(self.mapping.get("league_mapping", {}), name=name, category=Category.LEAGUES)



static_mapping = StaticMapping()

# if __name__ == "__main__":
    # sm = StaticMapping()
    # print("Testing Team Mapping:")
    # print(sm.team("Manchester United"))
    # print("=" * 10)
    # print("Testing League Mapping:")
    # print(sm.league("counter-strike"))
    # print("=" * 10)
    # print("Testing Stat Mapping:")
    # print(sm.stat("games played"))
    # print(sm.unmapped)






