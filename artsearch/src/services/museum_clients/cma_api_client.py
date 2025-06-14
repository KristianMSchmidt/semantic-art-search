from typing import Any, Tuple

from artsearch.src.services.museum_clients.base_client import (
    MuseumAPIClient,
    MuseumAPIClientError,
    ArtworkPayload,
    ParsedAPIResponse,
)


class CMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://openaccess-api.clevelandart.org/api/artworks/"
    BASE_SEARCH_URL = BASE_URL

    def get_thumbnail_url(self, inventory_number: str) -> str:
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
        work_types = [item["type"].lower()]
        return ArtworkPayload(
            object_number=item["accession_number"],
            titles=[{"title": item["title"], "language": "english"}],
            work_types=work_types,
            searchable_work_types=work_types,
            artist=[
                artist["description"].split("(")[0].strip()
                for artist in item["creators"]
            ],
            production_date_start=item["creation_date_earliest"],
            production_date_end=item["creation_date_latest"],
            thumbnail_url=str(item["images"]["web"]["url"]),
            museum="cma",
        )

    def _extract_items(self, raw_data: dict[str, Any]) -> ParsedAPIResponse:
        total_count = raw_data.get("info", {}).get("total", 0)
        items_list = raw_data.get("data", [])
        return ParsedAPIResponse(
            total_count=total_count,
            next_page_token=None,
            items_list=items_list,
        )
