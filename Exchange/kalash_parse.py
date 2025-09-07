class MarketHander:
    LOOP_MAPPER = {
        "over": "yes",
        "under": "no",
    }

    def __init__(self, market_name, market_object, series_ticker, titles, league, event_date, event_ticker, plural_player_line):
        self.market_name = market_name
        self.market_object = market_object
        self.series_ticker = series_ticker
        self.titles = titles
        self.league = league
        self.event_date = event_date
        self.event_ticker = event_ticker
        self.plural_player_line = plural_player_line

    def parse(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement this method.")

    @staticmethod
    def get_valid_markets():
        return ["Moneyline", "Spread", "Total", "Anytd", "2td"]

    def create_base(self):
        # Common base structure for all market types
        return {
            "series_ticker": self.series_ticker,
            "ticker": self.market_object.get("ticker"),
            "event_ticker": self.event_ticker,
            "match_title": self.titles.get(self.event_ticker).replace("at", "vs"),
            "event_date": self.event_date,
            "league": self.league,
            "market": self.market_name,
            "book_name": "kalashi",
        }

class SpreadHanlder(MarketHander):
    def parse(self):
        base = self.create_base()
        return [
            {
                **base,
                "line": -self.market_object.get("floor_strike") if option == "yes" else self.market_object.get("floor_strike"),
                "bet_team": SpreadHanlder._extract_team(self.market_object.get("yes_sub_title")) if option == "yes" else self._configure_spread(self.market_object.get("yes_sub_title")),
                "price": self.market_object.get(f"{option}_ask") / 100,
                "last_price": self.market_object.get("last_price") / 100,
                "volume": self.market_object.get("volume"),
                "volume_24h": self.market_object.get("volume_24h"),
                "liquidity": self.market_object.get("liquidity"),
            }

            for option in ["yes", "no"]
        ]

    @staticmethod
    def _extract_team(sub_title):
        split_raw_string = sub_title.split("wins")
        return split_raw_string[0].strip() if len(split_raw_string) > 0 else None

    def _configure_spread(self, sub_title):
        # Configure the spread team based on the match title - Extract the opposing team
        match_title = self.titles.get(self.event_ticker)
        teams = [t.strip() for t in match_title.split("vs")]
        current_team = SpreadHanlder._extract_team(sub_title)
        if not current_team:
            return None

        return next(team for team in teams if team != current_team)

class TouchdownHandler(MarketHander):
    def parse(self):
        base = self.create_base()
        market = base.pop("market")
        mapper = {
            "Anytd": "Anytime TD",
            "2td": "2+ TDs",
        }
        base["market"] = mapper.get(market, market)

        return [
            {
                **base,
                "bet_type": "over" if option == "yes" else "under",
                "bet_team": TouchdownHandler._extract_team(self.market_object.get("title")),
                "bet_player": self.market_object.get("yes_sub_title"),
                "line": 0.5 if not self.plural_player_line else 1.5,
                "price": self.market_object.get(f"{option}_ask") / 100,
                "last_price": self.market_object.get("last_price") / 100,
                "volume": self.market_object.get("volume"),
                "volume_24h": self.market_object.get("volume_24h"),
                "liquidity": self.market_object.get("liquidity"),
            }

            for option in ["yes", "no"]
        ]

    @staticmethod
    def _extract_team(title):
        raw_split = title.split(":")[0]
        current_team = raw_split.split("vs")
        return current_team[0].strip() if len(current_team) > 0 else None



class TotalHandler(MarketHander):
    # Handle Total markets
    def parse(self):
        base = self.create_base()
        return [
            {
                **base,
                "bet_type": option,
                "bet_team": None,
                "line": self.market_object.get("floor_strike"),
                "price": self.market_object.get(f"{MarketHander.LOOP_MAPPER.get(option)}_ask") / 100,
                "last_price": self.market_object.get("last_price") / 100,
                "volume": self.market_object.get("volume"),
                "volume_24h": self.market_object.get("volume_24h"),
                "liquidity": self.market_object.get("liquidity"),
            }

            for option in ["over", "under"]
        ]

class MoneylineHandler(MarketHander):
    # Handle Moneyline markets
    def parse(self):
        base = self.create_base()
        return [{
            **base,
            "bet_type": None,
            "line": None,
            "bet_team": self.market_object.get("yes_sub_title"),
            "price": self.market_object.get(f"yes_ask") / 100,
            "last_price": self.market_object.get("last_price") / 100,
            "volume": self.market_object.get("volume"),
            "volume_24h": self.market_object.get("volume_24h"),
            "liquidity": self.market_object.get("liquidity"),
        }]
