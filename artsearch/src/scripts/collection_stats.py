from collections import defaultdict
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.config import config


# Define source collection name
SOURCE_COLLECTION = config.qdrant_collection_name


def count_points(points):
    object_numbers = set()
    object_name_counts = defaultdict(int)
    for point in points:
        assert point.payload is not None
        object_names = [
            object_name.get("name").lower()
            for object_name in point.payload.get('object_names', [])
        ]
        for object_name in object_names:
            object_name_counts[object_name] += 1
        object_numbers.add(point.payload.get('object_number'))
    return object_name_counts, object_numbers


def fetch_point():
    points, _ = qdrant_client.scroll(
        collection_name=SOURCE_COLLECTION,
        scroll_filter=None,
        with_vectors=True,
        limit=10_000,
    )
    return points


def print_stats(object_name_counts, object_numbers, points_data):
    print("------ Collection stats ------")
    # Print the counts (ordered by number of points)
    for object_name, count in sorted(
        object_name_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"'{object_name}': {count}")

    # Print the total number of points
    print(f"Total number of artworks: {len(points_data)}")

    # Print the number of object_numbers (should be equal to the total number
    #  of artworks)
    print(f"Total number of unique object_numbers: {len(object_numbers)}")


if __name__ == "__main__":

    qdrant_service = get_qdrant_service()
    qdrant_client = qdrant_service.qdrant_client

    points = fetch_point()

    object_name_counts, object_numbers = count_points(points)

    print_stats(object_name_counts, object_numbers, points)
