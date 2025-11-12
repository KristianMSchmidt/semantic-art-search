"""Helper functions to format downloaded Qdrant payloads for frontend display."""

from qdrant_client import models

from artsearch.src.constants.museums import SUPPORTED_MUSEUMS
from artsearch.src.utils.work_type_utils import get_standardized_work_type
from artsearch.src.services.museum_clients.utils import (
    get_museum_page_url,
    get_museum_api_url,
)
from etl.services.bucket_service import get_bucket_image_url


def get_full_museum_name(museum_slug: str) -> str:
    """
    Get full museum name from slug.
    """
    for museum in SUPPORTED_MUSEUMS:
        if museum["slug"] == museum_slug.lower():
            return museum["full_name"]
    return museum_slug


def format_payload(payload: models.Payload | None) -> dict:
    """
    Make payload ready for display in the frontend.
    """
    if payload is None:
        raise ValueError("Payload cannot be None")

    production_date = payload.get("production_date", "")

    work_types = [
        get_standardized_work_type(name).capitalize() for name in payload["work_types"]
    ]

    thumbnail_url = get_bucket_image_url(
        payload["museum"], payload["object_number"], use_etl_bucket=False
    )

    source_url = get_museum_page_url(
        payload["museum"], payload["object_number"], payload["museum_db_id"]
    )
    api_url = get_museum_api_url(
        payload["museum"], payload["object_number"], payload["museum_db_id"]
    )
    return {
        "title": payload["title"],
        "artist": payload["artist"],
        "work_types": work_types,
        "thumbnail_url": thumbnail_url,
        "production_date": production_date,
        "object_number": payload["object_number"],
        "museum": get_full_museum_name(payload["museum"]),
        "museum_slug": payload["museum"],
        "museum_db_id": payload["museum_db_id"],
        "source_url": source_url,
        "api_url": api_url,
        "find_similar_query": f"{payload['museum']}:{payload['object_number']}",
    }


def format_payloads(payloads: list[models.Payload | None]) -> list[dict]:
    return [format_payload(payload) for payload in payloads]


def format_hit(hit: models.ScoredPoint) -> dict:
    formatted_hit = format_payload(hit.payload)
    formatted_hit.update({"score": round(hit.score, 3)})
    return formatted_hit


def format_hits(hits: list[models.ScoredPoint]) -> list[dict]:
    return [format_hit(hit) for hit in hits]
