from typing import Any
import requests
from artsearch.src.services.museum_clients.base_client import (
    ArtworkPayload,
)
from artsearch.src.services.museum_clients.utils import get_searchle_work_types
from artsearch.src.constants import SEARCHABLE_WORK_TYPES


MET_CLASSIFICATION_TO_WORK_TYPE = {
    "paintings": "painting",
    "miniatures": "miniature",
    "pastels": "pastel",
    "oil sketches on paper": "oil sketch on paper",
    "drawings": "drawing",
    "prints": "print",
}


class METAPIClient:
    BASE_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
    OBJECTS_URL = f"{BASE_URL}/objects"
    SEARCH_URL = f"{BASE_URL}/search"

    def __init__(self):
        self.http_session = requests.Session()

    def process_item(self, item: dict[str, Any]) -> ArtworkPayload:
        # Is public domain?
        if not item["isPublicDomain"]:
            raise ValueError("Item is not in public domain")

        # Thumbnail URL
        thumbnail_url = str(item["primaryImageSmall"])
        if not thumbnail_url:
            raise ValueError("Thumbnail URL is missing")

        # Object number
        object_number = item["accessionNumber"]
        if ":" in object_number:
            raise ValueError("Object number should not contain a colon")

        # Titles
        titles = [{"title": item["title"]}]

        # Work types
        classification = item["classification"].lower().strip()
        object_name = item["objectName"].lower().strip()
        print(
            f"Classification: {classification}, ObjectName: {object_name}",
            "Thumbnail URL:",
            thumbnail_url,
        )
        if classification:
            classification_split = [part.strip() for part in classification.split("&")]
            work_types = [
                MET_CLASSIFICATION_TO_WORK_TYPE[part] for part in classification_split
            ]
        elif object_name in SEARCHABLE_WORK_TYPES:
            work_types = [object_name]
        else:
            raise ValueError(
                f"Unsupported classification or object name: {classification}, {object_name}"
            )

        # Searchable work types
        searchable_work_types = get_searchle_work_types(work_types)
        print(f"Searchable work types: {searchable_work_types}")

        # Artist
        artist = [item["artistDisplayName"]]

        # Production dates
        production_date_start = int(item["objectBeginDate"])
        production_date_end = int(item["objectEndDate"])

        # Museum database ID
        museum_db_id = item["objectID"]

        return ArtworkPayload(
            object_number=object_number,
            titles=titles,
            work_types=work_types,
            searchable_work_types=searchable_work_types,
            artist=artist,
            production_date_start=production_date_start,
            production_date_end=production_date_end,
            thumbnail_url=thumbnail_url,
            museum="met",
            museum_db_id=museum_db_id,
        )

    def get_dept_object_ids(self, department_id: int) -> list[int]:
        """Fetch object IDs for a given department ID from the MET API."""
        url = f"{self.OBJECTS_URL}?departmentIds={department_id}"
        try:
            resp = self.http_session.get(url)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching department {department_id} object IDs: {e}")
            raise
        else:
            return resp.json().get("objectIDs", [])

    def get_item(self, object_id: int) -> dict[str, Any]:
        """Fetch a single artwork item from the MET API."""
        object_url = f"{self.OBJECTS_URL}/{object_id}"
        try:
            item = self.http_session.get(object_url, timeout=10)
            item.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching object {object_id}: {e}")
            raise
        else:
            return item.json()

    def get_object_ids_by_search(self, query_params: dict[str, Any]) -> list[int]:
        """Search for items in the MET collection using query parameters"""
        try:
            resp = self.http_session.get(self.SEARCH_URL, params=query_params)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Error searching items: {e}")
            raise
        else:
            return resp.json().get("objectIDs", [])
