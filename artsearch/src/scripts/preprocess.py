"""
Script for reducing the dimensionality of the SMK Artworks embeddings from 512D to 50D using UMAP.
"""

import umap
import numpy as np
from tqdm import tqdm
from qdrant_client.http.models import PointStruct
from artsearch.src.services.qdrant_service import get_qdrant_service
from sklearn.preprocessing import normalize

qdrant_service = get_qdrant_service()
qdrant_client = qdrant_service.qdrant_client

# Define collections
SOURCE_COLLECTION = "smk_artworks"
TARGET_COLLECTION = "smk_artworks_50d"

# Step 1: Fetch all points from the original collection
print("Fetching data from Qdrant...")
all_points = qdrant_service.qdrant_client.scroll(
    SOURCE_COLLECTION, scroll_filter=None, with_vectors=True, limit=10_000
)

vectors, metadata, ids = [], [], []

for point in all_points[0]:  # First item is the list of points
    vectors.append(point.vector)
    metadata.append(point.payload)  # Metadata remains unchanged
    ids.append(point.id)

vectors = np.array(vectors)  # Convert to NumPy array
vectors = normalize(vectors, norm="l2")  # Normalize embeddings

# Print ou the shape of the vectors
print(f"Loaded {len(vectors)} vectors with shape: {vectors.shape}")

# chek l2 norm of first vector
print(np.linalg.norm(vectors[0]))

# Step 2: Reduce dimensionality with UMAP
print(f"Reducing dimensionality from {vectors.shape[1]}D to 50D...")
umap_model = umap.UMAP(n_components=50, metric="euclidean", random_state=42)
vectors_50d = umap_model.fit_transform(vectors)

# # Step 3: Create a new collection in Qdrant
qdrant_service.create_qdrant_collection(
    collection_name=TARGET_COLLECTION,
    dimensions=50,
)

# # Step 4: Upload transformed data
print("Uploading transformed vectors to Qdrant...")
points = [
    PointStruct(id=ids[i], vector=vectors_50d[i].tolist(), payload=metadata[i])  # type: ignore
    for i in tqdm(range(len(ids)))
]
# TODO: Make metods
qdrant_client.upsert(collection_name=TARGET_COLLECTION, points=points)

print("Done! The 50D vectors are now stored in Qdrant.")
