from typing import Any

from artsearch.src.services.museum_clients.base_client import (
    MuseumAPIClient,
    MuseumAPIClientError,
    ArtworkPayload,
    ParsedAPIResponse,
)
from artsearch.src.services.museum_clients.utils import get_searchle_work_types


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
        work_types = [
            object_name.get("name").lower() for object_name in item["object_names"]
        ]
        return ArtworkPayload(
            object_number=item["object_number"],
            titles=item["titles"],
            work_types=work_types,
            searchable_work_types=get_searchle_work_types(work_types),
            artist=item["artist"],
            production_date_start=int(
                item["production_date"][0]["start"].split("-")[0]
            ),
            production_date_end=int(item["production_date"][0]["end"].split("-")[0]),
            thumbnail_url=str(item["image_thumbnail"]),
            museum="smk",
        )

    def _extract_items(self, raw_data: dict[str, Any]) -> ParsedAPIResponse:
        total_count = raw_data.get("found", 0)
        items_list = raw_data.get("items", [])
        return ParsedAPIResponse(
            total_count=total_count,
            next_page_token=None,
            items_list=items_list,
        )
