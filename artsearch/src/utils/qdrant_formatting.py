from qdrant_client import models


def format_payload(payload: models.Payload | None) -> dict:
    if payload is None:
        raise ValueError("Payload cannot be None")

    if payload["production_date_start"] == payload["production_date_end"]:
        period = payload["production_date_start"]
    else:
        period = (
            f"{payload['production_date_start']} - {payload['production_date_end']}"
        )

    return {
        "title": payload["titles"][0]["title"],
        "artist": ", ".join(payload["artist"]),
        "work_types": ", ".join(name.capitalize() for name in payload["work_types"]),
        "thumbnail_url": payload["thumbnail_url"],
        "period": period,
        "object_number": payload["object_number"],
        "museum": payload["museum"].upper(),
    }


def format_payloads(payloads: list[models.Payload | None]) -> list[dict]:
    return [format_payload(payload) for payload in payloads]


def format_hit(hit: models.ScoredPoint) -> dict:
    formatted_hit = format_payload(hit.payload)
    formatted_hit.update({"score": round(hit.score, 3)})
    return formatted_hit


def format_hits(hits: list[models.ScoredPoint]) -> list[dict]:
    return [format_hit(hit) for hit in hits]
