from PIL import Image
import requests
import logging

from qdrant_client import models
from qdrant_client.models import PointStruct

from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.museum_clients.factory import get_museum_client
from artsearch.src.config import config
from artsearch.src.scripts.upload_to_qdrant.upload_utils import generate_uuid5

logging.basicConfig(level=logging.WARNING)


def delete_altarpieces(collection_name: str = config.qdrant_collection_name):
    qdrant_service = get_qdrant_service()
    client = qdrant_service.qdrant_client
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="searchable_work_types",
                match=models.MatchAny(any=["altarpiece"]),
            )
        ]
    )
    # Get the payload of the points to be deleted
    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=query_filter,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )

    for point in points:
        # Delete the point with the specified ID
        client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=[point.id]),
        )
        print(f"Point with ID {point.id} deleted from collection {collection_name}")


def create_index(collection_name: str):
    qdrant_service = get_qdrant_service()
    client = qdrant_service.qdrant_client
    client.create_payload_index(
        collection_name=collection_name,
        field_name="object_number",
        field_schema="keyword",  # pyright: ignore
        wait=True,
    )


def copy(source_collection: str, destination_collection: str):
    # Retrieve all points (handle pagination for large datasets)
    qdrant_service = get_qdrant_service()
    qdrant_client = qdrant_service.qdrant_client

    batch_size = 1000
    offset = None

    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=source_collection,
            limit=batch_size,
            with_vectors=True,
            offset=offset,
        )
        if not points:
            break
        # Define new IDs (example: incrementing by 1000)
        updated_points = [
            PointStruct(
                id=generate_uuid5("smk", p.payload["object_number"]),  # type: ignore
                vector=p.vector,  # type: ignore
                payload=p.payload,
            )
            for p in points
        ]

        qdrant_client.upsert(
            collection_name=destination_collection, points=updated_points
        )

        print(f"Processed {len(points)} points")

        # Stop when the last batch is smaller than batch_size
        if len(points) < batch_size:
            break
        offset = next_offset


def make_favicon():
    # Initialize the SMK API client
    smk_client = get_museum_client("smk")

    # Get the thumbnail URL for the specified artwork
    object_number = "KMSr171"
    thumbnail_url = smk_client.get_thumbnail_url(object_number)

    # Fetch the image from the URL
    response = requests.get(thumbnail_url, stream=True)
    response.raise_for_status()  # Ensure we got a valid response

    # Open the image
    img = Image.open(response.raw)  # type: ignore

    # Resize image to favicon size (typically 32x32 or 48x48)
    favicon_size = (32, 32)  # You can adjust to (16,16) or (48,48) if needed
    img = img.resize(favicon_size, Image.LANCZOS)  # type: ignore

    # Save the image as favicon.ico
    img.save("artsearch/static/favicon.ico", format="ICO")

    print("Favicon saved as favicon.ico")


if "__main__" == "__main__":
    print("Running adhoc script")
