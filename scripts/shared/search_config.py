from src.services.qdrant_search_service import QdrantSearchService
from src.services.smk_api_client import SMKAPIClient
from src.services.clip_embedder import CLIPEmbedder
from src.utils import get_qdrant_client


def initialize_search_service(collection_name="smk_artworks") -> QdrantSearchService:
    """
    Initialize and return a QdrantSearchService instance.

    Args:
        collection_name (str): Name of the Qdrant collection to use.

    Returns:
        QdrantSearchService: Configured search service instance.
    """
    qdrant_client = get_qdrant_client()
    embedder = CLIPEmbedder()
    smk_api_client = SMKAPIClient()
    return QdrantSearchService(qdrant_client, embedder, smk_api_client, collection_name)
