"""
This script fetches data from the SMK API, processes it, and uploads it to a
Qdrant collection.
"""

import requests
from qdrant_client.http.models import PointStruct
from urllib.parse import urlencode
from typing import Any, Dict, List
import dotenv
from src.services.clip_embedder import CLIPEmbedder
import uuid
from src.utils import get_clip_embedder, get_qdrant_client

dotenv.load_dotenv()


def get_user_confirmation() -> None:
    """Prompt the user for confirmation before proceeding."""
    response = input("Do you want to proceed? (y/n): ")
    if response.lower() != "y":
        print("Exiting the program.")
        exit()
    print("Proceeding with the program...")


def fetch_data(api_url: str) -> Dict[str, Any]:
    """Fetch data from the SMK API and return it as JSON."""
    response = requests.get(api_url)
    response.raise_for_status()
    return response.json()


def process_items(data: Dict[str, Any], embedder: CLIPEmbedder) -> List[PointStruct]:
    """Process items from SMK API data and return a list of Qdrant PointStruct."""
    points = []
    for idx, item in enumerate(data.get("items", [])):
        try:
            # Prepare metadata for Qdrant payload
            payload = {
                "object_number": item["object_number"],
                "titles": item.get("titles", []),
                "object_names": item.get("object_names", []),
                "artist": item.get("artist", []),
                "production_date_start": item.get("production_date")[0]
                .get("start")
                .split("-")[0],
                "production_date_end": item.get("production_date")[0]
                .get("end")
                .split("-")[0],
                "thumbnail_url": item["image_thumbnail"],
            }
            # Make vector embedding from the thumbnail URL
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


def main():
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
    QUERY_PARAMS = {
        "keys": "*",
        "fields": ",".join(FIELDS),
        "filters": "[has_image:true],[object_names:maleri],[public_domain:true]",
        "range": f"[production_dates_end:{{{START_DATE};{END_DATE}}}]",
        "offset": 0,
        "rows": 250,  # Max is 2000
    }

    # Initialize Qdrant client
    qdrant_client = get_qdrant_client()

    # Initialize CLIP embedder
    embedder = get_clip_embedder()

    # Ensure the collection exists
    COLLECTION_NAME = "smk_artworks"
    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "size": 512,
            "distance": "Cosine",
        },
    )
    offset = 0
    total_points = 0

    while True:
        QUERY_PARAMS["offset"] = offset
        API_URL = f"{BASE_URL}?{urlencode(QUERY_PARAMS)}"
        data = fetch_data(API_URL)

        # Check if there are any items in the response
        if not data.get("items"):
            break

        # Process and upload points to Qdrant
        print(f"Processing items for offset {offset}...")
        points = process_items(data, embedder)

        # Bulk upsert to Qdrant
        if points:
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)

        total_points += len(points)

        # Check if we've retrieved all the data
        if offset + QUERY_PARAMS["rows"] >= data["found"]:
            break

        # Update offset for the next batch
        offset += QUERY_PARAMS["rows"]

    print(f"Total points uploaded: {total_points}")


if __name__ == "__main__":
    get_user_confirmation()
    main()
