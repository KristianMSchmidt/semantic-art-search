from typing import Any

from artsearch.src.services.museum_clients.base_client import (
    MuseumAPIClient,
    MuseumAPIClientError,
    ArtworkPayload,
    ParsedAPIResponse,
)


class CMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://openaccess-api.clevelandart.org/api/artworks/"
    BASE_SEARCH_URL = BASE_URL

    def get_object_url(self, object_number: str) -> str:
        return f"{self.BASE_URL}?accession_number={object_number}"

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
