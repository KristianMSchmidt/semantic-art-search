import requests
from functools import lru_cache
from artsearch.src.config import config

JINA_API_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-clip-v2"
JINA_DIMENSIONS = 256


@lru_cache(maxsize=50)
def _cached_jina_text_embedding(query: str) -> tuple[float, ...]:
    """Cache wrapper - returns tuple for hashability."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.jina_api_key}",
    }
    response = requests.post(
        JINA_API_URL,
        headers=headers,
        json={
            "input": [{"text": query}],
            "model": JINA_MODEL,
            "dimensions": JINA_DIMENSIONS,
        },
    )
    response.raise_for_status()
    return tuple(response.json()["data"][0]["embedding"])


class JinaEmbedder:
    def generate_text_embedding(self, query: str) -> list[float]:
        return list(_cached_jina_text_embedding(query))


@lru_cache(maxsize=1)
def get_jina_embedder() -> JinaEmbedder:
    return JinaEmbedder()
