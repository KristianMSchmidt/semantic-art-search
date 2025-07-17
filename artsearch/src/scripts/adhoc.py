from PIL import Image
import requests
import logging
import time

from qdrant_client import models
from qdrant_client.models import PointStruct

from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.museum_clients.factory import get_museum_client
from artsearch.src.config import config
from artsearch.src.scripts.upload_to_qdrant.upload_utils import generate_uuid5
from artsearch.src.services.bucket_service import BucketService

logging.basicConfig(level=logging.WARNING)


def delete_all_points_from_met():
    """
    Delete all points from the MET collection in Qdrant.
    This is a destructive operation and should be used with caution.
    """
    qdrant_service = get_qdrant_service()
    collection_name = config.qdrant_collection_name
    client = qdrant_service.qdrant_client

    # Fetch all points in the collection
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=1000,
        with_vectors=False,
        with_payload=True,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="museum",
                    match=models.MatchValue(value="met"),
                )
            ]
        ),
    )
    for point in points:
        assert point.payload is not None, "Point payload should not be None"
        print(point.payload["museum"])
        assert point.payload["museum"] == "met", "Point is not from the MET collection"
    point_ids = [point.id for point in points]
    breakpoint()
    client.delete(
        collection_name=collection_name,
        points_selector=models.PointIdsList(points=point_ids),
    )


def test_get_existing_values():
    qdrant_service = get_qdrant_service()
    collection_name = config.qdrant_collection_name
    values = [436236, 9999999999]
    existing_values = qdrant_service.get_existing_values(
        collection_name=collection_name,
        values=values,
        museum="met",
        id_key="museum_db_id",
    )
    print(f"Existing values in collection {collection_name}: {existing_values}")


def count_ids(collection_name: str = config.qdrant_collection_name) -> None:
    """
    Count number of unique qdrant IDs and unique "oject_numbers" in qdrant collection.
    """
    qdrant_service = get_qdrant_service()

    next_page_token = None

    qdrant_ids = set()
    object_numbers = set()
    num_points = 0

    while True:
        points, next_page_token = qdrant_service.fetch_points(
            collection_name, next_page_token, limit=1000, with_vectors=False
        )

        for point in points:
            qdrant_ids.add(point.id)
            assert point.payload is not None, "Point payload should not be None"
            object_number = point.payload.get("object_number")
            if object_number in object_numbers:
                print(
                    f"Duplicate object number found: {object_number} in point ID {point.id}"
                )
                breakpoint()
            object_numbers.add(point.payload["object_number"])
        num_points += len(points)
        if next_page_token is None:  # No more points left
            break
    print(f"Total points in collection {collection_name}: {num_points}")
    print(f"Unique IDs in collection {collection_name}: {len(qdrant_ids)}")
    print(
        f"Unique object numbers in collection {collection_name}: {len(object_numbers)}"
    )
    if len(qdrant_ids) != len(object_numbers):
        print(
            "Warning: The number of unique IDs does not match the number of unique object numbers."
        )
    else:
        print(
            "The number of unique IDs matches the number of unique object numbers. This is expected."
        )


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


def upload_all_thumbnails(collection_name: str = config.qdrant_collection_name) -> None:
    qdrant_service = get_qdrant_service()
    bucket_service = BucketService()

    next_page_token = None

    num_points = 0

    problematic_points = []
    while True:
        points, next_page_token = qdrant_service.fetch_points(
            collection_name, next_page_token, limit=100, with_vectors=False
        )
        for point in points:
            start_time = time.time()
            assert point.payload is not None
            # TODO: Change url to resized images at this point, if needed
            image_url = point.payload["thumbnail_url"]
            museum = point.payload["museum"]
            object_number = point.payload["object_number"]
            try:
                bucket_service.upload_thumbnail(
                    museum=museum,
                    object_number=object_number,
                    museum_image_url=image_url,
                )
            except Exception as e:
                problematic_points.append((museum, object_number, image_url))
                print(
                    f"Failed to upload thumbnail for point {point.id} with URL {image_url}"
                )

        num_points += len(points)

        print(f"Processed {len(points)} points, total so far: {num_points}")
        print(f"time taken for this batch: {time.time() - start_time:.2f} seconds")

        if next_page_token is None:  # No more points left
            break
    logging.info(
        f"Successfully updated {num_points} points in collection {collection_name}."
    )
    print(problematic_points)


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
    # count_ids()
