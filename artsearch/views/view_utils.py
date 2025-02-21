from django.http import HttpRequest
from typing import Callable
from artsearch.src.services.qdrant_service import QdrantService


def retrieve_offset(request: HttpRequest) -> int:
    offset = request.GET.get("offset", None)
    assert offset is not None
    offset = int(offset)
    return offset


def retrieve_search_action_url(
    request: HttpRequest, qdrant_service: QdrantService
) -> str:
    search_action_url = request.GET.get("search_action_url")
    assert search_action_url in ["text-search", "similarity-search"]
    return search_action_url


def retrieve_search_function(
    search_action_url: str, qdrant_service: QdrantService
) -> Callable:
    if search_action_url == "text-search":
        return qdrant_service.search_text
    else:
        return qdrant_service.search_similar_images
