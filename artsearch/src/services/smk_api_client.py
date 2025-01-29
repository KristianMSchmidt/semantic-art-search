import requests
from artsearch.src.utils.session_config import get_configured_session


class SMKAPIClientError(Exception):
    """Custom exception for SMKAPIClient errors."""
    pass


class SMKAPIClient:
    BASE_URL = "https://api.smk.dk/api/v1/art/"

    def __init__(self, http_session: requests.Session = None):
        self.http_session = http_session or get_configured_session()

    def get_thumbnail_url(self, object_number: str) -> str:
        """Fetch the thumbnail URL for a given object number."""
        if not object_number:
            raise SMKAPIClientError("Please enter an inventory number.")

        url = f"{self.BASE_URL}?object_number={object_number}"
        response = self.http_session.get(url)

        # Raise exception for HTTP errors (4xx, 5xx)
        response.raise_for_status()
        data = response.json()

        # Ensure 'items' key exists and contains at least one item
        if not data.get('items'):
            raise SMKAPIClientError(f"No artwork found with inventory number: {object_number}")

        # Extract thumbnail URL safely
        try:
            return data['items'][0]['image_thumbnail']
        except (KeyError, IndexError):
            raise SMKAPIClientError(f"Missing expected data for object number: {object_number}")
