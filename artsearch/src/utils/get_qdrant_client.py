from qdrant_client import QdrantClient
from artsearch.src.config import config


def get_qdrant_client():
    return QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)
