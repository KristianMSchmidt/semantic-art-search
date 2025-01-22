from qdrant_client import QdrantClient
from clip_embedder import CLIPEmbedder
from config import Config


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY)


def get_clip_embedder() -> CLIPEmbedder:
    return CLIPEmbedder(device=Config.DEVICE)
