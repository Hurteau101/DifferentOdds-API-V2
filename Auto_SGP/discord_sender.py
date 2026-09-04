import os
import pytz
from discordwebhook import Discord
from datetime import datetime, timezone
from dotenv import load_dotenv


class DiscordSGP:
    def __init__(self, production: bool):
        load_dotenv()

        # if production:
        #     self.webhook = os.getenv("AUTO_SGP_DISCORD_WEBHOOK_URL_PROD")
        # else:
        #     self.webhook = os.getenv("AUTO_SGP_DISCORD_WEBHOOK_URL_DEV")
        #
        # if not self.webhook:
        #     raise ValueError("DISCORD_WEBHOOK_URL not set in environment variables.")
        #
        # self.discord = Discord(url=self.webhook)
        WEBHOOK_URL = os.getenv("AUTO_SGP_DISCORD_WEBHOOK_URL_DEV")

        self.discord = Discord(url=WEBHOOK_URL)

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

    def _convert_to_unix(self, date_str: str):
        return int(datetime.fromisoformat(date_str.replace("Z", "+00:00")).timestamp())


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

    @staticmethod
    def format_ev(ev):
        return f"{(round(ev or 0, 2) + 0.0):+.2f}%"

    def _format_links(self, book_name:str, url:str):
        label = book_name.title()

        if isinstance(url, str):
            return [f"- [{label}]({url})"]
        if isinstance(url, dict):
            return [
                f"- [{label} {k.title()}]({v})"
                for k, v in url.items() if v
            ]

        return []

    def mapper(self, book_name:str):
        if not book_name:
            return ''

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

    def send_alert(self, slip: dict):
        if not slip:
            return None

        fields = []

        legs_text = "\n".join(
            f"**{i}.** {leg.get('normalized') or '—'}"
            for i, leg in enumerate(slip.get("legs", []), start=1)
        )

        odds = [
            f"- {book_name.title().replace("*", '')}: {self.format_american(book_data.get('odds'))} | {self.format_ev(book_data.get('ev'))} EV"
            for book_name, book_data in slip.get("weighted_sgp_odds").items()
        ]

        fields.extend([
            {
                "name": slip.get("event"),
                "value": f"<t:{self._convert_to_unix(slip.get('date'))}:D>",
                "inline": False
            },
            {
                "name": "",
                "value": legs_text,
                "inline": False
            },
            {
                "name": "Weighted Fair Value",
                "value": f"`{self.format_american(round(slip.get('weighted_fair_value'), 0))}`",
                "inline": True
            },
            {
                "name": "Non-Correlated Price",
                "value": f"`{self.format_american(slip.get('non_correlated_price'))}`",
                "inline": True
            },
            {
                "name": "SGP Odds",
                "value": f"```\n" + "\n".join(odds) + "\n```",
                "inline": False
            }
        ])

        if slip.get("median_non_met_books", {}):
            # print(
            #     slip.get("weighted_sgp_odds", {})
            # )
            odds = [
                f"- {book_name.title()}: {self.format_american(book_odds)}"
                for book_name, book_odds in slip.get("median_non_met_books").items()
            ]

            fields.append({
                "name": "Non-Weighted SGP Odds",
                "value": f"```\n" + "\n".join(odds) + "\n```",
                "inline": False
            })

        best_book = next(iter(slip.get("weighted_sgp_odds")), None)

        if best_book:
            link_url = slip.get("sgp_links", {}).get(best_book)
            links = self._format_links(best_book, link_url) if best_book else []

            if links:
                fields.append({
                    "name": "Best Book Link",
                    "value": "\n".join(links),
                    "inline": False,
                })

        embed = {
            "title": f"{len(slip.get('legs'))}-Leg SGP • {slip.get('league')}",
            "color": 0x2ECC71,
            "author": {"name": "SGP Bot • V3.0"},
            "fields": fields,
            "footer": {"text": "Powered by BettorOdds"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        mention = f"{self.mapper(best_book)}" if best_book else ""

        try:
            self.discord.post(
                content=f"\n\n{mention}" if mention else "",
                embeds=[embed]
            )
        except Exception as e:
            print("Error sending Discord alert:", e)

# if __name__ == "__main__":
#     DiscordSGP(production=False).send_alert(data, sgp_links=sgp_links)