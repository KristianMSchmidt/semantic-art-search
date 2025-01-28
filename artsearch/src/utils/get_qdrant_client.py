from qdrant_client import QdrantClient
from artsearch.src.config import Config


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY)


