from artsearch.src.services.qdrant_search_service import QdrantSearchService
from artsearch.src.services.smk_api_client import SMKAPIClient
from artsearch.src.services.clip_embedder import CLIPEmbedder
from artsearch.src.utils.get_qdrant_client import get_qdrant_client


# Initialize the search service once (Singleton-like behavior)
print("Initializing QdrantSearchService (only once)...")

qdrant_client = get_qdrant_client()
embedder = CLIPEmbedder()
smk_api_client = SMKAPIClient()
collection_name = "smk_artworks"

search_service = QdrantSearchService(qdrant_client, embedder, smk_api_client, collection_name)
