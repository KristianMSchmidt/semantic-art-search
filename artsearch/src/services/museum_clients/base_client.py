import requests
from typing import Any, Optional, Literal
from urllib.parse import urlencode
from abc import ABC, abstractmethod
from pydantic import BaseModel, ValidationError
from artsearch.src.utils.session_config import get_configured_session

MuseumName = Literal["smk", "cma", "rma", "all"]


class MuseumAPIClientError(Exception):
    """Custom exception for museum API client errors."""

    pass


class ArtworkPayload(BaseModel):
    object_number: str
    titles: list[dict]
    work_types: list[str]
    artist: list[str]
    production_date_start: int
    production_date_end: int
    thumbnail_url: str
    museum: str


class MuseumQueryResponse(BaseModel):
    total: int
    next_page_token: Optional[str]
    items: list[ArtworkPayload]


class ParsedAPIResponse(BaseModel):
    total_count: int
    next_page_token: Optional[str]
    items_list: list[dict[str, Any]]


class MuseumAPIClient(ABC):
    """Abstract base class for museum API clients."""

    BASE_SEARCH_URL: str

    def __init__(self, http_session: Optional[requests.Session] = None):
        self.http_session = http_session or get_configured_session()

    @abstractmethod
    def get_thumbnail_url(self, inventory_number: str) -> str:
        """Fetch the thumbnail URL for a given inventory number."""
        pass

    @abstractmethod
    def _process_item(self, item: dict[str, Any]) -> ArtworkPayload | None:
        """Process a single item fetched from a museum API."""
        pass

    @abstractmethod
    def _extract_items(self, raw_data: dict[str, Any]) -> ParsedAPIResponse:
        """
        Extracts the total count, next page token, and items from the raw API response.
        """
        pass

    def _process_raw_data(self, raw_data: dict[str, Any]) -> MuseumQueryResponse:
        """Generic method to process raw data, now shared across subclasses."""
        parsed_query_response = self._extract_items(raw_data)

        total_count = parsed_query_response.total_count
        next_page_token = parsed_query_response.next_page_token
        items = parsed_query_response.items_list

        artwork_payloads = []
        for item in items:
            try:
                artwork_payload = self._process_item(item)
                if artwork_payload is None:
                    continue
                artwork_payloads.append(artwork_payload)
            except (KeyError, AssertionError, ValidationError) as e:
                print(f"Error processing item: {e}")

        return MuseumQueryResponse(
            total=total_count, next_page_token=next_page_token, items=artwork_payloads
        )

    def fetch_processed_data(
        self, query_template: dict[str, Any]
    ) -> MuseumQueryResponse:
        """Fetch and process data from the museum using the shared method."""
        raw_data = _fetch_data_raw(
            self.BASE_SEARCH_URL, self.http_session, query_template
        )
        return self._process_raw_data(raw_data)


def _fetch_data_raw(
    base_url: str, http_session: requests.Session, query_template: dict[str, Any]
) -> dict[str, Any]:
    """Utility function to fetch raw API data"""
    api_url = f"{base_url}?{urlencode(query_template)}"
    try:
        response = http_session.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise MuseumAPIClientError(f"Error fetching data from {base_url}: {e}")
