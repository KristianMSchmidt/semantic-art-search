import requests
from typing import Any
from urllib.parse import urlencode
from artsearch.src.utils.session_config import get_configured_session


class SMKAPIClientError(Exception):
    """Custom exception for SMKAPIClient errors."""

    pass


class SMKAPIClient:
    BASE_URL = "https://api.smk.dk/api/v1/art/"
    BASE_SEARCH_URL = f"{BASE_URL}search/"

    def __init__(self, http_session: requests.Session | None = None):
        self.http_session = http_session or get_configured_session()

    def get_thumbnail_url(self, object_number: str) -> str:
        """Fetch the thumbnail URL for a given object number."""
        assert object_number, "Object number must be provided"

        url = f"{self.BASE_URL}?object_number={object_number}"
        response = self.http_session.get(url)

        # Raise exception for HTTP errors (4xx, 5xx)
        response.raise_for_status()
        data = response.json()

        # Ensure 'items' key exists and contains at least one item
        if not data.get('items'):
            raise SMKAPIClientError(
                f"No artwork found with inventory number: {object_number}"
            )

        # Extract thumbnail URL safely
        try:
            return data['items'][0]['image_thumbnail']
        except (KeyError, IndexError):
            raise SMKAPIClientError(
                f"Missing expected data for object number: {object_number}"
            )

    def fetch_data(self, query_template: dict[str, Any]) -> dict[str, Any] | None:
        """Use SMK's search endpoint to fetch artwork data and return it as JSON."""
        api_url = f"{self.BASE_SEARCH_URL}?{urlencode(query_template)}"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None
