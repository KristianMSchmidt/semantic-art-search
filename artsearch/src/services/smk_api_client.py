import requests
from artsearch.src.utils.session_config import get_configured_session


class SMKAPIClient:
    BASE_URL = "https://api.smk.dk/api/v1/art/"

    def __init__(self, http_session: requests.Session = None):
        self.http_session = http_session or get_configured_session()

    def get_thumbnail_url(self, object_number: str) -> str:
        """Fetch the thumbnail URL for a given object number."""
        url = f"{self.BASE_URL}?object_number={object_number}"
        response = self.http_session.get(url)
        response.raise_for_status()
        data = response.json()
        return data['items'][0]['image_thumbnail']
