import requests
from typing import Any, Optional, Literal, Tuple
from urllib.parse import urlencode
from abc import ABC, abstractmethod
from pydantic import BaseModel, ValidationError
from artsearch.src.utils.session_config import get_configured_session

MuseumName = Literal["smk", "cma", "all"]


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
    items: list[ArtworkPayload]


class MuseumAPIClient(ABC):
    """Abstract base class for museum API clients."""

    BASE_URL: str
    BASE_SEARCH_URL: str

    def __init__(self, http_session: Optional[requests.Session] = None):
        self.http_session = http_session or get_configured_session()

    @abstractmethod
    def get_thumbnail_url(self, inventory_number: str) -> str:
        """Fetch the thumbnail URL for a given inventory number."""
        pass

    @abstractmethod
    def _process_item(self, item: dict[str, Any]) -> ArtworkPayload:
        """Process a single item fetched from a museum API."""
        pass

    @abstractmethod
    def _extract_items(
        self, raw_data: dict[str, Any]
    ) -> Tuple[int, list[dict[str, Any]]]:
        """
        Extract the total count of items and the list of artworks from the raw API response.

        Returns:
            tuple: (total_count: int, items_list: list of artwork dictionaries)
        """
        pass

    def _process_raw_data(self, raw_data: dict[str, Any]) -> MuseumQueryResponse:
        """Generic method to process raw data, now shared across subclasses."""
        total_count, items = self._extract_items(
            raw_data
        )  # Extract total count and items dynamically
        artwork_payloads = []

        for item in items:
            try:
                artwork_payload = self._process_item(item)
                artwork_payloads.append(artwork_payload)
            except (KeyError, AssertionError, ValidationError) as e:
                print(f"Error processing item: {e}")

        return MuseumQueryResponse(total=total_count, items=artwork_payloads)

    def fetch_processed_data(
        self, query_template: dict[str, Any]
    ) -> MuseumQueryResponse:
        """Fetch and process data from the museum using the shared method."""
        raw_data = _fetch_data_raw(
            self.BASE_SEARCH_URL, self.http_session, query_template
        )
        return self._process_raw_data(raw_data)


class SMKAPIClient(MuseumAPIClient):
    BASE_URL = "https://api.smk.dk/api/v1/art/"
    BASE_SEARCH_URL = f"{BASE_URL}search/"

    def get_thumbnail_url(self, inventory_number: str) -> str:
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

    def _process_item(self, item: dict[str, Any]) -> ArtworkPayload:
        return ArtworkPayload(
            object_number=item["object_number"],
            titles=item["titles"],
            work_types=[
                object_name.get("name").lower() for object_name in item["object_names"]
            ],
            artist=item["artist"],
            production_date_start=int(
                item["production_date"][0]["start"].split("-")[0]
            ),
            production_date_end=int(item["production_date"][0]["end"].split("-")[0]),
            thumbnail_url=str(item["image_thumbnail"]),
            museum="smk",
        )

    def _extract_items(
        self, raw_data: dict[str, Any]
    ) -> Tuple[int, list[dict[str, Any]]]:
        """Extracts the total count and the list of artworks from SMK's API response."""
        total_count = raw_data.get(
            "found", 0
        )  # Extracts total number of artworks found
        items_list = raw_data.get("items", [])  # Extracts the list of artwork items
        return total_count, items_list


class CMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://openaccess-api.clevelandart.org/api/artworks/"
    BASE_SEARCH_URL = BASE_URL

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

    def _process_item(self, item: dict[str, Any]) -> ArtworkPayload:
        return ArtworkPayload(
            object_number=item["accession_number"],
            titles=[{"title": item["title"], "language": "english"}],
            work_types=[item["type"].lower()],
            artist=[
                artist["description"].split("(")[0].strip()
                for artist in item["creators"]
            ],
            production_date_start=item["creation_date_earliest"],
            production_date_end=item["creation_date_latest"],
            thumbnail_url=str(item["images"]["web"]["url"]),
            museum="cma",
        )

    def _extract_items(
        self, raw_data: dict[str, Any]
    ) -> Tuple[int, list[dict[str, Any]]]:
        """Extracts the total count and the list of artworks from CMA's API response."""
        total_count = raw_data.get("info", {}).get(
            "total", 0
        )  # Extracts total number of artworks found
        items_list = raw_data.get("data", [])  # Extracts the list of artwork items
        return total_count, items_list


# Utility functions
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


def get_museum_client(museum: MuseumName) -> SMKAPIClient | CMAAPIClient:
    if museum == "smk":
        return SMKAPIClient()
    elif museum == "cma":
        return CMAAPIClient()
    else:
        raise ValueError(f"Unsupported museum: {museum}")


def get_metadata_and_museum(
    object_number: str, museum_filter: MuseumName
) -> Tuple[str, MuseumName]:
    """
    Get metadata for a given object number without knowing the museum.
    This is slow (loops through museums), so only use it when necessary.
    If museum_filter is not "all", this is our best guess, so we start with it.

    Currently, this function only fetches the thumbnail URL, but it could be
    generalized to fetch all metadata if needed.

    This function will currently only be called, when user searches for items
    similar to item that is not already in the qdrant database.
    """
    if museum_filter != "all":
        museums: list[MuseumName] = [museum_filter, "smk", "cma"]
    else:
        museums: list[MuseumName] = ["smk", "cma"]

    for museum in museums:
        museum_client = get_museum_client(museum)
        print(f"Trying {museum} for object number: {object_number}")
        try:
            thumbnail_url = museum_client.get_thumbnail_url(object_number)
            return thumbnail_url, museum
        except Exception:
            continue
    raise MuseumAPIClientError(
        f"No artwork found with inventory number: {object_number}"
    )
