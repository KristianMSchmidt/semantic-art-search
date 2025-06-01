from artsearch.src.constants import WORK_TYPES_DICT, SUPPORTED_MUSEUMS
from qdrant_client import models


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

    if payload["production_date_start"] == payload["production_date_end"]:
        period = payload["production_date_start"]
    else:
        period = (
            f"{payload['production_date_start']} - {payload['production_date_end']}"
        )
    work_types = ", ".join(
        get_work_type_translation(name).capitalize() for name in payload["work_types"]
    )
    return {
        "title": payload["titles"][0]["title"],
        "artist": ", ".join(payload["artist"]),
        "work_types": work_types,
        "thumbnail_url": payload["thumbnail_url"],
        "period": period,
        "object_number": payload["object_number"],
        "museum": get_full_museum_name(payload["museum"]),
    }


def format_payloads(payloads: list[models.Payload | None]) -> list[dict]:
    return [format_payload(payload) for payload in payloads]


def format_hit(hit: models.ScoredPoint) -> dict:
    formatted_hit = format_payload(hit.payload)
    formatted_hit.update({"score": round(hit.score, 3)})
    return formatted_hit


def format_hits(hits: list[models.ScoredPoint]) -> list[dict]:
    return [format_hit(hit) for hit in hits]
