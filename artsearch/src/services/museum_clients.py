import requests
from typing import Any, Optional
from urllib.parse import urlencode
from abc import ABC, abstractmethod
from artsearch.src.utils.session_config import get_configured_session


class MuseumAPIClientError(Exception):
    """Custom exception for museum API client errors."""

    pass


class MuseumAPIClient(ABC):
    """Abstract base class for museum API clients."""

    BASE_URL: str

    def __init__(self, http_session: Optional[requests.Session] = None):
        self.http_session = http_session or get_configured_session()

    @abstractmethod
    def get_thumbnail_url(self, inventory_number: str) -> str:
        """Fetch the thumbnail URL for a given inventory number."""
        pass

    @staticmethod
    def _fetch_data(
        base_url: str, http_session: requests.Session, query_template: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Utility method to fetch artwork data from an API."""
        api_url = f"{base_url}?{urlencode(query_template)}"
        try:
            response = http_session.get(api_url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise MuseumAPIClientError(
                f"Error fetching data from {base_url}: {e}"
            ) from e


class SMKAPIClient(MuseumAPIClient):
    BASE_URL = "https://api.smk.dk/api/v1/art/"
    BASE_SEARCH_URL = f"{BASE_URL}search/"

    def get_thumbnail_url(self, inventory_number: str) -> str:
        """Fetch the thumbnail URL for a given inventory number."""
        if not inventory_number:
            raise ValueError("Inventory number must be provided.")

        url = f"{self.BASE_URL}?object_number={inventory_number}"
        response = self.http_session.get(url)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            raise MuseumAPIClientError(
                f"No artwork found with inventory number: {inventory_number}"
            )

        try:
            return items[0]["image_thumbnail"]
        except KeyError:
            raise MuseumAPIClientError(
                f"Missing thumbnail data for inventory number: {inventory_number}"
            )

    def fetch_data(self, query_template: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Use SMK's search endpoint to fetch artwork data."""
        return self._fetch_data(self.BASE_SEARCH_URL, self.http_session, query_template)


class CMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://openaccess-api.clevelandart.org/api/artworks/"

    def get_thumbnail_url(self, inventory_number: str) -> str:
        """Fetch the thumbnail URL for a given inventory number."""
        if not inventory_number:
            raise ValueError("Inventory number must be provided.")

        url = f"{self.BASE_URL}?accession_number={inventory_number}"
        response = self.http_session.get(url)
        response.raise_for_status()
        data = response.json()

        items = data.get("data", [])
        if not items:
            raise MuseumAPIClientError(
                f"No artwork found with inventory number: {inventory_number}"
            )

        try:
            return items[0]["images"]["web"]["url"]
        except KeyError:
            raise MuseumAPIClientError(
                f"Missing thumbnail data for inventory number: {inventory_number}"
            )

    def fetch_data(self, query_template: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Use CMA's search endpoint to fetch artwork data."""
        return self._fetch_data(self.BASE_URL, self.http_session, query_template)
