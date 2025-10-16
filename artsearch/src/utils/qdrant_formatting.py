"""Helper functions to format downloaded Qdrant payloads for frontend display."""

from qdrant_client import models

from artsearch.src.constants import WORK_TYPES_DICT, SUPPORTED_MUSEUMS
from artsearch.src.services.museum_clients.utils import get_museum_page_url
from etl.services.bucket_service import get_bucket_image_url


def get_full_museum_name(museum_slug: str) -> str:
    """
    Get full museum name from slug.
    """
    for museum in SUPPORTED_MUSEUMS:
        if museum["slug"] == museum_slug.lower():
            return museum["full_name"]
    return museum_slug


def get_work_type_translation(work_type: str) -> str:
    """
    Get work type in English singular form.
    """
    try:
        return WORK_TYPES_DICT[work_type]["eng_sing"]
    except KeyError:
        return work_type


def format_payload(payload: models.Payload | None) -> dict:
    """
    Make payload ready for display in the frontend.
    """
    if payload is None:
        raise ValueError("Payload cannot be None")

    production_date = payload.get("production_date", "")

    work_types = [
        get_work_type_translation(name).capitalize() for name in payload["work_types"]
    ]

    thumbnail_url = get_bucket_image_url(
        payload["museum"], payload["object_number"], use_etl_bucket=False
    )

    source_url = get_museum_page_url(
        payload["museum"], payload["object_number"], payload.get("museum_db_id", None)
    )
    return {
        "title": payload["title"],
        "artist": payload["artist"],
        "work_types": work_types,
        "thumbnail_url": thumbnail_url,
        "production_date": production_date,
        "object_number": payload["object_number"],
        "museum": get_full_museum_name(payload["museum"]),
        "source_url": source_url,
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
