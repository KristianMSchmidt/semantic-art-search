import hashlib
import json

from etl.models import MetaDataRaw


def compute_hash_of_json(data: dict) -> str:
    """Compute a stable hash of a JSON object"""
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def store_raw_data(museum_slug: str, object_id: str, raw_json: dict) -> bool:
    """
    Store or update raw data in the database.
    Returns True if the data was changed (indicating a re-embedding is needed),
    """
    raw_hash = compute_hash_of_json(raw_json)

    existing = MetaDataRaw.objects.filter(
        museum_slug=museum_slug, museum_object_id=object_id
    ).first()
    if existing and existing.raw_hash == raw_hash:
        return False  # no update needed

    MetaDataRaw.objects.update_or_create(
        museum_slug=museum_slug,
        museum_object_id=object_id,
        defaults={
            "raw_json": raw_json,
            "raw_hash": raw_hash,
        },
    )
    return True  # indicates change
