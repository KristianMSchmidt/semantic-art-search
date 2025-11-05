from functools import lru_cache
from qdrant_client import QdrantClient
from artsearch.src.config import config


@lru_cache(maxsize=1)
def get_qdrant_client():
    """
    Get Qdrant client (cached singleton).

    IMPORTANT: This function is cached to follow Qdrant best practices.

    Why caching is required:
    - Client initialization is expensive (~400ms): establishes connections,
      performs TLS handshake, validates auth, sets up connection pool
    - Qdrant documentation recommends reusing client instances, not recreating
    - The client manages its own connection pool with automatic reconnection

    Connection lifecycle:
    - The cached client holds a connection pool (managed by HTTPX internally)
    - Stale/dead connections are automatically detected and replaced
    - Connection failures raise exceptions that are caught by error handlers
    - No manual cleanup needed - connections managed automatically

    Thread safety:
    - QdrantClient is thread-safe and designed for concurrent use
    - Connection pool handles multiple simultaneous requests

    See: https://qdrant.tech/documentation/guides/distributed-deployment/#client-configuration
    """
    return QdrantClient(url=config.qdrant_url, api_key=config.qdrant_api_key)
