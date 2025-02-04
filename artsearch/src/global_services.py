from qdrant_client import QdrantClient
from artsearch.src.services.clip_embedder import CLIPEmbedder
from artsearch.src.services.qdrant_search_service import QdrantSearchService
from artsearch.src.services.smk_api_client import SMKAPIClient
from artsearch.src.config import Config


# Create and cache the heavy instances once per process
clip_embedder_instance = CLIPEmbedder()
qdrant_client_instance = QdrantClient(
    url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY
)
smk_api_client_instance = SMKAPIClient()

search_service_instance = QdrantSearchService(
    qdrant_client=qdrant_client_instance,
    embedder=clip_embedder_instance,
    smk_api_client=smk_api_client_instance,
    collection_name="smk_artworks",
)
