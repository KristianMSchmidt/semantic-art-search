from collections import defaultdict
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.config import config

# =============================================================================
# STEP 1: FETCH DATA FROM THE ORIGINAL COLLECTION (512D embeddings)
# =============================================================================

# Initialize Qdrant service
qdrant_service = get_qdrant_service()
qdrant_client = qdrant_service.qdrant_client

# Define source collection name
SOURCE_COLLECTION = config.qdrant_collection_name


# Function to count points by each object_name
def count_points_by_object_name():
    object_name_counts = defaultdict(int)
    for point in points_data:
        assert point.payload is not None
        object_names = [
            object_name.get("name").lower()
            for object_name in point.payload.get('object_names', [])
        ]
        for object_name in object_names:
            object_name_counts[object_name] += 1
    return object_name_counts


# =============================================================================
# MAIN EXECUTION
# =============================================================================

# Fetch data from Qdrant
print("Fetching data from Qdrant...")
points_data, _ = qdrant_client.scroll(
    collection_name=SOURCE_COLLECTION,
    scroll_filter=None,
    with_vectors=True,
    limit=10_000,
)

# Count points by each object_name
object_name_counts = count_points_by_object_name()

# Print the counts
for object_name, count in object_name_counts.items():
    print(f"Number of points for object name '{object_name}': {count}")
