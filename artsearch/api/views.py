from django.http import JsonResponse

from artsearch.src.config import config
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.services.museum_clients.utils import (
    get_museum_page_url,
    get_museum_api_url,
)
from etl.services.bucket_service import get_bucket_image_url


qdrant_service = QdrantService(collection_name=config.qdrant_collection_name_app)


def artwork_detail_view(request, museum_slug: str, object_number: str):
    items = qdrant_service.get_items_by_object_number(
        object_number=object_number,
        object_museum=museum_slug,
        with_payload=True,
        limit=1,
    )

    if not items:
        return JsonResponse({"error": "Artwork not found"}, status=404)

    payload = items[0].payload

    if payload is None:
        return JsonResponse({"error": "Artwork not found"}, status=404)

    return JsonResponse(
        {
            **payload,
            "thumbnail_url": get_bucket_image_url(
                museum_slug, object_number, use_etl_bucket=False
            ),
            "source_url": get_museum_page_url(
                museum_slug, object_number, payload["museum_db_id"]
            ),
            "api_url": get_museum_api_url(
                museum_slug, object_number, payload["museum_db_id"]
            ),
        }
    )
