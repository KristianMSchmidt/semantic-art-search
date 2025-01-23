"""
This script fetches data from the SMK API, processes it, and uploads it
to a Qdrant collection.
"""

import requests
from qdrant_client.http.models import PointStruct
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from src.services.clip_embedder import CLIPEmbedder
import uuid
from src.utils import get_qdrant_client

# Load environment variables
load_dotenv()

# Constants
BASE_URL = "https://api.smk.dk/api/v1/art/search/"
FIELDS = [
    "titles",
    "artist",
    "object_names",
    "production_date",
    "object_number",
    "image_thumbnail",
]
START_DATE = "1000-01-01T00:00:00.000Z"
END_DATE = "2026-12-31T23:59:59.999Z"
COLLECTION_NAME = "smk_artworks"
QUERY_TEMPLATE = {
    "keys": "*",
    "fields": ",".join(FIELDS),
    "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
    "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
    "offset": 0,
    "rows": 250,  # Max is 2000
}


def get_user_confirmation() -> None:
    """Prompt the user for confirmation before proceeding."""
    response = input("Do you want to proceed? (y/n): ").strip().lower()
    if response != "y":
        print("Exiting the program.")
        exit()
    print("Proceeding with the program...")


def fetch_data(api_url: str) -> Optional[Dict[str, Any]]:
    """Fetch data from the SMK API and return it as JSON."""
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def prepare_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare payload for Qdrant PointStruct."""
    return {
        "object_number": item["object_number"],
        "titles": item.get("titles", []),
        "object_names": item.get("object_names", []),
        "artist": item.get("artist", []),
        "production_date_start": item["production_date"][0]["start"].split("-")[0],
        "production_date_end": item["production_date"][0]["end"].split("-")[0],
        "thumbnail_url": item["image_thumbnail"],
    }


def process_items(data: Dict[str, Any], embedder: CLIPEmbedder) -> List[PointStruct]:
    """Process items from SMK API data and return a list of Qdrant PointStruct."""
    points = []
    for item in data.get("items", []):
        try:
            payload = prepare_payload(item)
            vector = embedder.generate_thumbnail_embedding(
                item["image_thumbnail"], item["object_number"]
            )
            if vector is not None:
                points.append(
                    PointStruct(id=str(uuid.uuid4()), payload=payload, vector=vector)
                )
            else:
                print(
                    f"Skipping item {item['object_number']} due to embedding failure."
                )
        except KeyError as e:
            print(f"Missing key in item: {e}")
    return points


def create_qdrant_collection(client) -> None:
    """Create Qdrant collection (if it doesn't exist)."""
    exists = client.collection_exists(collection_name=COLLECTION_NAME)
    if not exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={"size": 512, "distance": "Cosine"},
        )


def main() -> None:
    """Main entry point of the script."""
    embedder = CLIPEmbedder()
    qdrant_client = get_qdrant_client()

    create_qdrant_collection(qdrant_client)

    offset = 0
    total_points = 0

    while True:
        QUERY_TEMPLATE["offset"] = offset
        api_url = f"{BASE_URL}?{urlencode(QUERY_TEMPLATE)}"
        data = fetch_data(api_url)

        if not data or not data.get("items"):
            break

        print(f"Processing items for offset {offset}...")
        points = process_items(data, embedder)

        if points:
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
            total_points += len(points)

        if offset + QUERY_TEMPLATE["rows"] >= data["found"]:
            break

        offset += QUERY_TEMPLATE["rows"]

    print(f"Total points uploaded: {total_points}")


if __name__ == "__main__":
    get_user_confirmation()
    main()
