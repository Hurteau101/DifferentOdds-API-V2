class ApiResponseMixin:
    """Provides a reusable check_api_response implementation for subclasses of BookBase."""

    def check_api_response(self, sportsbook: str, results: list):
        if not results:
            self._api_call_log(sportsbook=sportsbook, error_details="No data received from API")
            return None

        if isinstance(results, dict):
            if not results.get("success"):
                self._api_call_log(sportsbook=sportsbook, error_details=results.get("error"))
                return None
        else:
            for response in results:
                if not response.get("success"):
                    self._api_call_log(sportsbook=sportsbook, error_details=response.get("error"))
                    return None

        return results