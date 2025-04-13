from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.museum_clients import SMKAPIClient, CMAAPIClient
from artsearch.src.utils.get_qdrant_client import get_qdrant_client
from artsearch.src.config import config


def get_qdrant_service() -> QdrantService:
    return QdrantService(
        qdrant_client=get_qdrant_client(),
        smk_api_client=SMKAPIClient(),
        cma_api_client=CMAAPIClient(),
        embedder=get_clip_embedder(),
        collection_name=config.qdrant_collection_name,
    )
