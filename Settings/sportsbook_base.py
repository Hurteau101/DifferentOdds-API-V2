import json
from abc import ABC

import aiohttp.client
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from Settings.Mixin.mixins import ApiResponseMixin
from Settings.book_base import BookBase
from Settings.sportsbook_config import SportsbookConfig


class SportsbookBase(BookBase, ApiResponseMixin, ABC):
    def __init__(self, request_type, sportsbook_name: str, log_directory="Sportsbook Logs", log_name=None):
        self.book_data = SportsbookConfig.get_sportsbook_provider(sportsbook_name)
        super().__init__(request_type, log_directory=log_directory, log_name=log_name)
        load_dotenv()

    @staticmethod
    def parser(text_data: str, key_name: str = None, is_inner: bool = False) -> dict:
        """
        Parser to help reformat a text block into JSON format.
        :param key_name: The key name to use for the parsed data.
        :param text_data: The raw text data to parse.
        :param is_inner: Whether to parse inner JSON data.
        """
        if is_inner and not key_name:
            raise ValueError("Key name must be provided for parsing.")

        outer = json.loads(text_data)

        if is_inner:
            inner = json.loads(outer[key_name])
            return inner

        return outer

    def check_api_response(self, sportsbook: str, results: list):
        return ApiResponseMixin.check_api_response(self, sportsbook, results)

    async def api_caller(
            self,
            session,
            url,
            headers,
            payload=None,
            data=None,
            params=None,
            method="GET",
            use_parser=False,
            key_name=None,
            is_inner=False
    ):
        if use_parser and key_name is None:
            raise ValueError("key_name must be provided when use_parser is True.")

        request_args = {}

        if payload is not None:
            request_args["json"] = payload

        if data is not None:
            request_args["data"] = data

        if params is not None:
            request_args["params"] = params


        method = method.upper()
        if method == "POST":
            request = session.post
        else:
            request = session.get

        async with request(url, headers=headers, **request_args) as response:
            if response.status != 200:
                return None

            try:
                if use_parser:
                    data = await response.text()
                    return self.parser(data, key_name=key_name, is_inner=is_inner)

                return await response.json()
            except aiohttp.client.ContentTypeError:
                data = await response.text()
                if use_parser:
                    return self.parser(data, key_name=key_name, is_inner=is_inner)

                return json.loads(data)


    def _pph_login(self, payload: dict, sportsbook_name: str, additional_headers: dict = None, login_key_word_check: str = None):
        """
        Used for PPH sportsbooks that require login via ASP.NET forms.
        :param payload: The payload containing login credentials and any additional required fields.
        :param sportsbook_name: The name of the sportsbook for logging purposes.
        :param additional_headers: Any additional headers to include in the login request.
        :param login_key_word_check: A keyword to check in cookies to verify successful login.
        """

        if not payload:
            raise ValueError("Payload for login cannot be empty.")

        login_url = self.book_data.url.get("login_url")
        session = requests.Session()
        request_session = session.get(login_url)
        soup = BeautifulSoup(request_session.text, "html.parser")

        def find_values(name):
            hidden_tag = soup.find("input", {"name": name})
            return hidden_tag["value"] if hidden_tag else ""


        starter_payload = {
            "__VIEWSTATE": find_values("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": find_values("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": find_values("__EVENTVALIDATION"),
        }

        starter_payload.update(payload)


        if additional_headers:
            self.book_data.headers.update(additional_headers)

        session.post(login_url, data=payload, headers=self.book_data.headers)

        if login_key_word_check and login_key_word_check not in session.cookies.get_dict():
            self.file_logger.log(
                sportsbook=sportsbook_name,
                message=f"Login failed for {sportsbook_name} Sportsbook."
            )
            return None

        return session.cookies.get_dict()