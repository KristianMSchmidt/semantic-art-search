from qdrant_client import models

from artsearch.src.constants import WORK_TYPES_DICT, SUPPORTED_MUSEUMS
from artsearch.src.services.bucket_service import get_cdn_thumbnail_url


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


def get_source_url(
    museum_slug: str, object_number: str, museum_db_id: str | None = None
) -> str | None:
    """
    Returns the URL to the artwork's page at the source museum, based on slug and object number / museum_db_id.
    """
    if museum_slug == "met" and museum_db_id is None:
        raise ValueError(
            "museum_db_id must be provided for the Metropolitan Museum of Art"
        )
    match museum_slug:
        case "smk":
            return f"https://open.smk.dk/artwork/image/{object_number}"
        case "cma":
            return f"https://www.clevelandart.org/art/{object_number}"
        case "rma":
            return f"https://www.rijksmuseum.nl/en/collection/{object_number}"
        case "met":
            return f"https://www.metmuseum.org/art/collection/search/{museum_db_id}"
        case _:
            return None  # Unknown museum


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
    work_types = [
        get_work_type_translation(name).capitalize() for name in payload["work_types"]
    ]

    cdn_thumbnail_url = get_cdn_thumbnail_url(
        payload["museum"], payload["object_number"]
    )

    source_url = get_source_url(
        payload["museum"], payload["object_number"], payload.get("museum_db_id", None)
    )
    return {
        "title": payload["titles"][0]["title"],
        "artist": ", ".join(payload["artist"]),
        "work_types": work_types,
        "thumbnail_url": cdn_thumbnail_url,
        "period": period,
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
