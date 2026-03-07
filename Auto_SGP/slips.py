from collections import defaultdict
from itertools import product

class SlipMapper:
    def _grouper(self, filtered_data: dict, grouped_fields: list) -> dict:
        """
        Generic grouper function to group by specified fields.
        ["event", "date"] - No same team restriction
        ["event", "date", "team"] - Same team restriction

        :param filtered_data: The filtered data to group.
        :param grouped_fields: The list of fields to group by.
        :return: The grouped data as a dictionary.
        """
        grouped = defaultdict(list)

        for market in filtered_data.values():
            key = tuple(market.get(field) for field in grouped_fields)
            grouped[key].append(market)

        return dict(grouped)

    def build_leg_combinations(self, market_data: list, stat_types: list, use_same_player: bool,
                               validate_players: bool):
        """
        Build all possible combinations of player legs based on specified stat types.

        validate_players=True & use_same_player=True - All legs must have the same player.
        validate_players=True & use_same_player=False - All legs must have different players.

        :param validate_players: Whether to validate players in combinations.
        :param market_data: The market data to build combinations from.
        :param stat_types: The list of stat types to consider for combinations.
        :param use_same_player: If True, skip combinations with the same player across legs.
        :return: Returns a list of valid player leg combinations.
        """

        legs = [
            [market for market in market_data if market.get("bet_info", "").lower() == leg]
            for leg in stat_types
        ]

        if any(len(leg) == 0 for leg in legs):
            return []

        combinations = []

        for combo in product(*legs):
            if not validate_players:
                combinations.append(combo)
                continue

            players = [(market.get("player"), market.get("bet_info").lower())
                       for market in combo if market.get("player")]

            if use_same_player:
                # Check if all player names are the same (If greater than 1, it means different players)
                if len({p[0] for p in players}) != 1:
                    continue

                # Check if all bet_info are the same. If not the same length of players then different is the same.
                # This prevents same stat types for same players (Ex. over 3.5 and over 4.5 for same player)
                if len({p[1] for p in players}) != len(players):
                    continue
            else:
                # Check if all players are different. If not the same length then the same players exist more than once.
                if len({p[0] for p in players}) != len(players):
                    continue

            combinations.append(combo)

        return combinations

    # Built for multi-legs slips
    def slip_selection(self, filtered_data: dict, stat_types: list, use_same_player: bool,
                       grouped_fields: list, validate_players: bool) -> list:
        """
        Build different slips based on stats types and grouping fields.
        :param filtered_data: The filtered data to use for combinations.
        :param stat_types: The list of stat types to consider.
        :param use_same_player: Use the same player for the combinations.
        :param grouped_fields: The list of fields to group by.
        :param validate_players: Whether to validate players in combinations.
        :return: A list of built slip combinations.
        """
        pairs = []
        grouped = self._grouper(filtered_data, grouped_fields=grouped_fields)

        for key, markets in grouped.items():
            group_map = dict(zip(grouped_fields, key))

            event = group_map.get("event")
            date = group_map.get("date")
            # team = group_map.get("team")

            combos = self.build_leg_combinations(
                markets,
                stat_types,
                use_same_player=use_same_player,
                validate_players=validate_players
            )


            for combo in combos:
                entry = {
                    "event": event,
                    "date": date,
                    "league": combo[0].get("league"),
                    "changes": {"movement": [], "new": []}
                }



                for i, market in enumerate(combo, start=1):
                    if not market.get("team"):
                        entry[f"team_{i}"] = None
                    else:
                        entry[f"team_{i}"] = market.get("team")

                    if not market.get("market_type"):
                        entry[f"market_type_{i}"] = None
                    else:
                        entry[f"market_type_{i}"] = market.get("market_type")

                    for name, value in market.get("changes").items():
                        entry["changes"][value.lower()].append(name)


                for index, market in enumerate(combo, start=1):
                    entry[f"total_odds_{index}"] = market.get("total_odds")
                    entry[f"game_key_{index}"] = market.get("game_key")
                    entry[f"stat_name_{index}"] = market.get("stat_name")
                    entry[f"stat_type_{index}_line"] = market.get("stat")
                    entry[f"stat_type_{index}_nvig_map"] = market.get("nvig_map")
                    entry[f"stat_type_{index}_books"] = market.get("books")
                    # entry["changes"] = market.get("changes")


                pairs.append(entry)

        return pairs
