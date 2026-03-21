import re
from datetime import datetime, timezone
import os
import pytz
from discordwebhook import Discord
from dotenv import load_dotenv


class DiscordSGP:
    def __init__(self, production):
        load_dotenv()

        if production:
            self.webhook = os.getenv("AUTO_SGP_DISCORD_WEBHOOK_URL_PROD")
        else:
            self.webhook = os.getenv("AUTO_SGP_DISCORD_WEBHOOK_URL_DEV")

        if not self.webhook:
            raise ValueError("DISCORD_WEBHOOK_URL not set in environment variables.")

        self.discord = Discord(url=self.webhook)

    def _convert_to_utc(self, event_date):
        """
        Converts the event date to US/Eastern timezone and formats it as YYYY-MM-DD.
        :param event_date: Event date in ISO format or datetime object.
        :return: Returns the formatted date string.
        """
        try:
            if isinstance(event_date, str):
                event_date = event_date.replace("Z", "+00:00")
                event_utc = datetime.fromisoformat(event_date)
            elif isinstance(event_date, datetime):
                event_utc = event_date
            else:
                event_utc = None

            if event_utc:
                eastern = pytz.timezone("US/Eastern")
                game_start_eastern = event_utc.astimezone(eastern)
                game_date = game_start_eastern.strftime("%Y-%m-%d")
            else:
                game_date = "N/A"

        except Exception:
            game_date = None

        return game_date

    def extract_legs(self, sgp_data):
        """Extracts the legs of the SGP from the provided data."""
        legs = []

        i = 1
        while f"stat_name_{i}" in sgp_data:
            name = sgp_data[f"stat_name_{i}"]
            line = sgp_data[f"stat_type_{i}_line"]
            direction = sgp_data[f"stat_{i}_direction"]

            legs.append(f"{line} {name} [{direction}]")
            i += 1

        return legs

    @staticmethod
    def format_american(odds_val):
        """Ensure American odds are always displayed properly (+120 / -110)."""
        if odds_val is None:
            return "N/A"
        try:
            val = float(odds_val)
            val = int(val) if val.is_integer() else val
            return f"+{val}" if val > 0 else str(val)
        except Exception:
            return str(odds_val)

    def mapper(self, book_name:str):
        role_mapper = {
            "fanatics": os.getenv("FANATICS_ROLE_ID"),
            "fanduel": os.getenv("FANDUEL_ROLE_ID"),
            "hardrock": os.getenv("HARDROCK_ROLE_ID"),
            "draftkings": os.getenv("DRAFTKINGS_ROLE_ID"),
            "kambi": os.getenv("KAMBI_ROLE_ID"),
            "onyxodds": os.getenv("ONYX_ROLE_ID"),
            "betmgm": os.getenv("BETMGM_ROLE_ID"),
            "novig": os.getenv("NOVIG_ROLE_ID"),
            "prophetx": os.getenv("PROPHETX_ROLE_ID"),
            "thescore": os.getenv("THESCORE_ROLE_ID"),
            "caesars": os.getenv("CAESARS_ROLE_ID"),

        }

        role_id = role_mapper.get(book_name.lower())
        return f"<@&{role_id}>" if role_id else ""

    def send_alert(self, sgp_data):
        event_date = self._convert_to_utc(sgp_data.get("date", "N/A"))
        weighted_fair_value = sgp_data.get("weighted_fair_value", 0)
        fair_parlay_price = sgp_data.get("fair_parlay_price", 0)


        if weighted_fair_value >= 0:
            weighted_fair_value_odds = f"+{round(weighted_fair_value, 2)}"
        else:
            weighted_fair_value_odds = f"-{round(weighted_fair_value, 2)}"

        if fair_parlay_price >= 0:
            fair_non_correlated_odd = f"+{round(fair_parlay_price, 2)}"
        else:
            fair_non_correlated_odd = f"-{round(fair_parlay_price, 2)}"

        legs = self.extract_legs(sgp_data)
        bet_lines = "\n".join(
            [f"**Bet {i + 1}:** {leg}" for i, leg in enumerate(legs)]
        )

        # previous_message = "*(SGP already sent but odds have moved)*\n" if sgp_data.get("already_sent") else ""

        fields = []

        # if previous_message:
        #     fields.append({
        #         "name": "Disclaimer",
        #         "value": previous_message,
        #         "inline": False
        #     })

        # Build Fields
        fields.extend([
            {
                "name": "Game Details",
                "value": f"**Date:** "
                         f"{event_date}\n**League:** {sgp_data.get('league', 'N/A')}",
                "inline": False
            },
            {
                "name": "Bet Details",
                "value": bet_lines,
                "inline": False
            },
            {
                "name": "Weighted Fair Value",
                "value": f"**{weighted_fair_value_odds}**",
            },
            {
                "name": "Fair Non Correlated Parlay Price",
                "value": f"**{fair_non_correlated_odd}**",
            }
        ])

        odds_lines = []

        discord_data = sgp_data.get("ev_results", {})
        sorted_ev = dict(sorted(discord_data.items(), key=lambda x: x[1]['ev'], reverse=True))

        for book, odds in sorted_ev.items():
            if isinstance(odds, dict):
                american = odds.get("odds")
            else:
                american = odds

            if american is None:
                american_str = "N/A"
            elif int(american) >= 0:
                american_str = f"+{int(american)}"
            else:
                american_str = str(int(american))

            ev_value = odds.get("ev")
            if isinstance(ev_value, (int, float)):
                ev_str = f"{ev_value:.2f}% EV"
            else:
                ev_str = "N/A EV"

            odds_lines.append(f"- {book.title()}: {american_str} | {ev_str}")

        formatted_non_met = []
        for entry in sgp_data.get("non_met_books", []):
            for book_name, book_odds in entry.items():
                formatted_non_met.append(
                    f"- {book_name.title()}: {self.format_american(book_odds)}"
                )

        fields.append({
            "name": "SGP Odds",
            "value": f"```\n" + "\n".join(odds_lines) + "\n```",
            "inline": False
        })

        if formatted_non_met:
            fields.append({
                "name": "Negative EV Non-Weighted SGP Odds",
                "value": f"```\n" + "\n".join(formatted_non_met) + "\n```",  # stays inside code block
                "inline": False
            })

        formatted_links = []
        for link_book_name, link_url in sgp_data.get("filtered_links").items():
            # Draftkings are broken on discord for the time being.
            if link_book_name == "draftkings":
                continue

            # Temp condiiton for caesars desktop only link
            if link_book_name == "caesars":
                formatted_links.append(
                    f"- [{link_book_name.title()} (Desktop Only)]({link_url})"
                )

                continue

            if isinstance(link_url, str):
                formatted_links.append(
                    f"- [{link_book_name.title()}]({link_url})"
                )
            elif isinstance(link_url, dict):
                mobile = link_url.get("mobile")
                desktop = link_url.get("desktop")

                formatted_links.append(
                    f"- [{link_book_name.title()} Mobile]({mobile})\n"
                    f"- [{link_book_name.title()} Desktop]({desktop})"
                )


        if formatted_links:
            fields.append({
                "name": "SGP Links",
                "value": "\n".join(formatted_links),
                "inline": False
            })

        fields.append({
            "name": "WARNING",
            "value": f"**Please verify all SGP sent during BETA**",
            "inline": False
        })


        embed = {
            "title": f"{sgp_data.get('event', 'N/A')}",
            "color": 0x2ECC71,
            "author": {"name": "SGP Bot BETA • V2.0"},
            "fields": fields,
            "footer": {"text": "Powered by BettorOdds"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        roles = [
            self.mapper(book_name)
            for book_name, odds in sorted_ev.items()
            if odds.get("ev", 0) >= sgp_data.get("minimum_ev")
        ]

        mentions = " ".join(roles)

        if mentions:
            mentions_block = f"\n\n{mentions}"
        else:
            mentions_block = ""

        try:
            self.discord.post(
                content=mentions_block,
                embeds=[embed]
            )
        except Exception as e:
            print("Error sending Discord alert:", e)
