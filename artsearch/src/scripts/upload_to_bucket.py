import logging
import time
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.bucket_service import (
    upload_thumbnail,
)


COLLECTION_NAME = "artworks_dev_2"


def upload_all_thumbnails() -> None:
    qdrant_service = get_qdrant_service()

    next_page_token = None

    num_points = 0

    problematic_points = []
    while True:
        points, next_page_token = qdrant_service.fetch_points(
            COLLECTION_NAME, next_page_token, limit=100, with_vectors=False
        )
        for point in points:
            start_time = time.time()
            id = point.id
            assert point.payload is not None
            # TODO: Change url to resized images at this point, if needed
            image_url = point.payload["thumbnail_url"]
            museum = point.payload["museum"]
            object_number = point.payload["object_number"]
            try:
                upload_thumbnail(
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
        f"Successfully updated {num_points} points in collection {COLLECTION_NAME}."
    )
    print(problematic_points)


if __name__ == "__main__":
    # upload_all_thumbnails()
