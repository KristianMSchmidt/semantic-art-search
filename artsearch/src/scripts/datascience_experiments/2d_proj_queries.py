import umap
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import normalize
from sklearn.decomposition import PCA
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.config import config

# =============================================================================
# STEP 0: CONFIGURATION
# Choose the first projection method: 'UMAP' or 'PCA'
FIRST_PROJECTION_METHOD = 'PCA'
# =============================================================================

# =============================================================================
# STEP 1: FETCH DATA FROM QDRANT (512D EMBEDDINGS)
# =============================================================================
qdrant_service = get_qdrant_service()
qdrant_client = qdrant_service.qdrant_client

print("Fetching data from Qdrant...")
points_data, _ = qdrant_client.scroll(
    config.qdrant_collection_name, scroll_filter=None, with_vectors=True, limit=10_000
)

vectors_512, metadata_list, ids = [], [], []
for point in points_data:
    vectors_512.append(point.vector)
    metadata_list.append(point.payload)
    ids.append(point.id)

vectors_512 = np.array(vectors_512)
vectors_512 = normalize(vectors_512, norm="l2")
print(f"Loaded {len(vectors_512)} vectors with shape: {vectors_512.shape}")

# =============================================================================
# STEP 2: REDUCE DIMENSIONALITY FROM 512D TO 50D
# =============================================================================
if FIRST_PROJECTION_METHOD == 'UMAP':
    print("Reducing dimensionality from 512D to 50D using UMAP...")
    umap_model_50d = umap.UMAP(n_components=50, metric="euclidean", random_state=42)
    vectors_50d = umap_model_50d.fit_transform(vectors_512)
else:
    print("Reducing dimensionality from 512D to 50D using PCA...")
    pca_model = PCA(n_components=50, random_state=42)
    vectors_50d = pca_model.fit_transform(vectors_512)

# =============================================================================
# STEP 3: FURTHER REDUCE FROM 50D TO 2D FOR VISUALIZATION
# =============================================================================
print("Reducing dimensionality from 50D to 2D for visualization...")
umap_model_2d = umap.UMAP(n_components=2, metric="euclidean", random_state=42)
vectors_2d = umap_model_2d.fit_transform(vectors_50d)

# =============================================================================
# STEP 4: EMBED TEXT QUERIES AND PROJECT TO 2D
# =============================================================================
print("Embedding text queries...")
clip_embedder = get_clip_embedder()
queries = [
    'Ship',
    'Grayscale ship',
    'Portrait',
    'Grayscale portrait',
    'Group of People',
    'Landscape',
    'Grayscale landscape',
    'Still Life',
    'Animal',
    'Building',
    'Orientalism',
    'Cubism',
    'Watercolor',
    'Bust',
]
embedded_queries = [clip_embedder.generate_text_embedding(query) for query in queries]
embedded_queries = normalize(np.array(embedded_queries), norm="l2")

if FIRST_PROJECTION_METHOD == 'UMAP':
    query_50d = umap_model_50d.transform(embedded_queries)
else:
    query_50d = pca_model.transform(embedded_queries)

query_2d = umap_model_2d.transform(query_50d)
print("Query embedding projection complete.")

# =============================================================================
# STEP 5: PLOT SCATTER WITH HOVER FUNCTIONALITY
# =============================================================================
plt.figure(figsize=(21, 15))

default_color, query_colors = "lightgray", [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "brown",
    "pink",
    "cyan",
    "magenta",
    "yellow",
    "black",
    "lime",
    "olive",
    'teal',
]
default_size, query_size = 2, 150

# Plot artwork embeddings
scatter = plt.scatter(
    vectors_2d[:, 0],  # type: ignore
    vectors_2d[:, 1],  # type: ignore
    c=default_color,
    s=default_size,
    alpha=0.6,
    edgecolors="k",
    linewidth=0.5,
)

# Plot query embeddings with unique colors
query_scatter = []
for i, query_point in enumerate(query_2d):
    qs = plt.scatter(
        query_point[0],
        query_point[1],
        c=query_colors[i],
        s=query_size,
        marker='X',
        edgecolors="black",
        label=queries[i],
    )
    query_scatter.append(qs)

# =============================================================================
# STEP 6: ADD LEGEND AND SHOW PLOT
# =============================================================================
plt.legend(loc="upper right", title="Query Mappings", fontsize="large")
plt.title("2D UMAP Projection with Hover Annotations and Queries", fontsize=16)
plt.xlabel("UMAP Dimension 1", fontsize=12)
plt.ylabel("UMAP Dimension 2", fontsize=12)
plt.show()
print("Done!")


# =============================================================================
# STEP 7: SAVE THE PLOT TO A FILE
# plt.savefig("2d_proj_queries.png")
# =============================================================================
