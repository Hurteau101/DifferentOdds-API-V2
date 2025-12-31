import re
from abc import ABC, abstractmethod

import unicodedata


class MarketHandler(ABC):
    def __init__(self, event_data: dict):
        self._store_handlers: dict = {}
        self.event_data = event_data

        if self.event_data.get("event"):
            self.event_data["event"] = self._clean_event_name(self.event_data.get("event", ""))

        self.key = self._generate_key(self.event_data.get("event", ""), self.event_data.get("common", {}).get("date", ""),
                                 self.event_data.get("common", {}).get("league", ""))

        self.event_data.update(**self._split_teams(self.event_data.get("event", "")))
        self.line = self.event_data.get("common", {}).get("line")


        self.team_1 = self.event_data.get("team_1", "")
        self.team_2 = self.event_data.get("team_2", "")
        self.event_data.get("common", {}).update({
            "team_1": self.team_1,
            "team_2": self.team_2,
        })

    def clean_and_normalize_name(self, name):
        if not name:
            return name

        nfkd_form = unicodedata.normalize('NFD', name)
        return ''.join([c for c in nfkd_form if not unicodedata.combining(c)])


    def _extract_player_data(self, opposite: bool, line=None):
        player = self.event_data.get("yes_sub_title", "")
        direction = "over" if not opposite else "under"

        if not line:
            raw_line = re.findall(r'-?\d+\.?\d*', self.event_data.get("yes_sub_title", ""))

            # If line is None or empty - Means its a 0.5 line
            if not raw_line:
                line = 0.5
            else:
                line = float(raw_line[0]) if raw_line else None

                # Since Kalshi uses lines of 35+ we need to subtract 0.5 to make an over/under line.
                if line and "+" in self.event_data.get("yes_sub_title", ""):
                    line -= 0.5



        if ":" in player:
            player = player.split(":", 1)[0].strip()

        bet_info = f"{direction} {line}" if line is not None else ""
        # player_team = self.event_data.get("ticker").split("-")[-1][0:3] if self.event_data.get("ticker") else ""

        # CHECK THIS ONCE TD LINES ARE OUT
        # player_team = self.event_data.get("ticker").split("-", 3)[2][0:3] if self.event_data.get("ticker") else ""
        return {"player": self.clean_and_normalize_name(player), "line": line, "bet_info": bet_info}
        # return {"player": self.clean_and_normalize_name(player), "line": line, "bet_info": bet_info, "player_team": player_team}


    def _generate_key(self, event_name, date, league) -> str:
        """Generate a unique key for the event based on its name and date."""
        modified_event_name = event_name.replace(" ", "_").lower()
        modified_date = date.replace("-", "_")
        return f"{modified_event_name}_{league.lower()}_{modified_date}"


    def _clean_event_name(self, event_name) -> str:
        """Remove market name and unnecessary characters from event name."""
        # return event_name.replace(self.market_name, "").replace(":", "").strip().replace(" at ", " vs ")
        event_name = event_name.split(":")[0]
        return event_name.replace(" at ", " vs ").strip()


    def _split_teams(self, event_name: str) -> dict:
        """Split event name into two teams based on common delimiters."""
        team_1, team_2 = re.split(r' vs | at ', event_name, flags=re.IGNORECASE)
        return {"team_1": team_1.strip(), "team_2": team_2.strip()}

    @abstractmethod
    def format_data(self, **kwargs):
        raise NotImplementedError("Subclasses must implement this method.")

# Registry to hold market handlers
MARKET_REGISTRY: dict[str, type[MarketHandler]] = {}

# Register a class as a handler for each market
def register_handler(market_name: str):
    # Create a decorator that registers the given class as a handler for each market
    def decorator(cls):
        if market_name in MARKET_REGISTRY:
            raise ValueError(f"Handler for {market_name} already registered.")

        cls.market_name = market_name
        MARKET_REGISTRY[market_name] = cls
        return cls
    return decorator

# Create an instance of a handler for a given market
def make_handler(market_name: str, event_data: dict) -> MarketHandler:
    if market_name not in MARKET_REGISTRY:
        raise ValueError(f"No handler registered for {market_name}. Available handlers: {list(MARKET_REGISTRY.keys())}")

    return MARKET_REGISTRY[market_name](event_data=event_data)


#####
# kwargs.get("opposite") - We use to get the opposite bet info (Ex. Bears +3 instead of Bears -3)
#####


@register_handler("Spread")
class SpreadHandler(MarketHandler):
    def format_data(self, **kwargs):
        if kwargs.get("opposite"):
            primary_team = self.team_1 if self.team_1 not in self.event_data.get("yes_sub_title", "") else self.team_2
            bet_info = f"+{self.line} {primary_team}"
        else:
            primary_team = self.team_1 if self.team_1 in self.event_data.get("yes_sub_title", "") else self.team_2
            bet_info = f"-{self.line} {primary_team}"

        return {
            "key": self.key,
            "event": self.event_data.get("event", ""),
            **self.event_data.get("common", {}),
            "bet_info": bet_info,
        }

@register_handler("Total Points")
class TotalLineHandler(MarketHandler):
    def format_data(self, **kwargs):
        direction = "over" if "over" in self.event_data.get("yes_sub_title", "").lower() else "under"

        if kwargs.get("opposite"):
            opposite_direction = "under" if direction == "over" else "over"
            bet_info = f"{opposite_direction} {self.line}"
        else:
            bet_info = f"{direction} {self.line}"

        return {
            "key": self.key,
            "event": self.event_data.get("event", ""),
            **self.event_data.get("common", {}),
            "bet_info": bet_info,
        }

@register_handler("Anytime Touchdown Scorer")
class AnytimeTDdownHandler(MarketHandler):
    def format_data(self, **kwargs):
        ##### COMMENT OUT ONCE TD LINES ARE OUT ##
        player = self.event_data.get("yes_sub_title", "")
        direction = "over" if not kwargs.get("opposite") else "under"
        market_name = self.event_data.get("common", {}).get("market")
        line = 0.5 if market_name == "Anytime Touchdown Scorer" else 1.5 if market_name is not None else None
        bet_info = f"{direction} {line}" if line is not None else ""
        # player_team = self.event_data.get("ticker").split("-")[-1][0:3] if self.event_data.get("ticker") else ""

        # self.event_data.get("common", {}).update(
        #     {"player": player, "line": line, "bet_info": bet_info, "player_team": player_team}
        # )

        self.event_data.get("common", {}).update(
            {"player": player, "line": line, "bet_info": bet_info}
        )

        ##########################################
        ##### UNCOMMENT ONCE TD LINES ARE OUT ##
        # market_name = self.event_data.get("common", {}).get("market")
        # line = 0.5 if market_name == "Anytime Touchdown Scorer" else 1.5 if market_name is not None else None
        # player_data = self._extract_player_data(opposite=kwargs.get("opposite"), line=line)
        # self.event_data.get("common", {}).update(player_data)
        ############################################

        return {
            "key": self.key,
            "event": self.event_data.get("event", ""),
            **self.event_data.get("common", {}),
        }

@register_handler("Two or More Touchdowns Scorer")
class TwoPlusTDdownHandler(AnytimeTDdownHandler):
    pass

@register_handler("Player Markets")
class PlayerMarkets(MarketHandler):
    def format_data(self, **kwargs):
        player_data = self._extract_player_data(opposite=kwargs.get("opposite"))
        self.event_data.get("common", {}).update(player_data)

        return {
            "key": self.key,
            "event": self.event_data.get("event", ""),
            **self.event_data.get("common", {}),
        }

@register_handler("Points")
class PlayerPoints(PlayerMarkets):
    pass

@register_handler("Assists")
class PlayerAssists(PlayerMarkets):
    pass

@register_handler("Rebounds")
class PlayerRebounds(PlayerMarkets):
    pass

@register_handler("Three Pointers")
class PlayerThrees(PlayerMarkets):
    pass

@register_handler("Double Doubles")
class PlayerDD(PlayerMarkets):
    pass

@register_handler("First Goal Scorer")
class PlayerFirstGoalScorer(PlayerMarkets):
    pass

@register_handler("Anytime Goal")
class PlayerAnytimeGoal(PlayerMarkets):
    pass

@register_handler("Moneyline")
class MoneylineHandler(MarketHandler):
    def format_data(self):
        return {
            "key": self.key,
            "event": self.event_data.get("event", ""),
            **self.event_data.get("common", {}),
            "bet_info": self.team_1 if self.team_1 == self.event_data.get("yes_sub_title") else self.team_2,
        }


if __name__ == "__main__":
    spread_cls = make_handler("Spread", "NBA Finals")

