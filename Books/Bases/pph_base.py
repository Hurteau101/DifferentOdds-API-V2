import json

import requests
from bs4 import BeautifulSoup
from curl_cffi.requests import Session
from Books.Bases.book_base import BookBase
from Monitoring.monitoring import create_sentry_message
from Utils.request_caller import SportbookRequestType
from Books.Bases.sportsbook_base import SportsbooksBookBase


class PPHBookBase(SportsbooksBookBase):
    def __init__(self, book_name: str, request_type: SportbookRequestType):
        super().__init__(book_name=book_name, request_type=request_type)

    def pph_login_helper(self, payload: dict, sportsbook_name: str, additional_headers: dict = None,
                   login_key_word_check: str = None):
        """
        Used for PPH sportsbooks that require login via ASP.NET forms.
        :param payload: The payload containing login credentials and any additional required fields.
        :param sportsbook_name: The name of the sportsbook for logging purposes.
        :param additional_headers: Any additional headers to include in the login request.
        :param login_key_word_check: A keyword to check in cookies to verify successful login.
        """
        def find_values(name):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""

        if not payload:
            raise ValueError("Payload for login cannot be empty.")

        with Session(impersonate="chrome120") as session:
            response = session.get(self.book_data.url.get("login_url"))
            soup = BeautifulSoup(response.text, "html.parser")


            starter_payload = {
                "__VIEWSTATE": find_values("__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": find_values("__EVENTVALIDATION"),
            }

            starter_payload.update(payload)

            if additional_headers:
                self.book_data.headers.update(additional_headers)

            print(starter_payload)
            response = session.post("https://bettheguys.com/Login.aspx", data=payload, headers=self.book_data.headers)

            print(response.text)

            if login_key_word_check and login_key_word_check not in session.cookies.get_dict():
                create_sentry_message(
                    tag_key=self.book_data.name,
                    tag_value="login_failure",
                    message="Couldn't login",
                    level="error"
                )
                return None
            print(session.cookies.get_dict())
            return session.cookies.get_dict()