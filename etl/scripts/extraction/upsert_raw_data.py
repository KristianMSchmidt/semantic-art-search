import hashlib
import json
from django.utils import timezone

from etl.models import MetaDataRaw


def compute_hash_of_json(data: dict) -> str:
    """Compute a stable hash of a JSON object"""
    normalized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_hash_of_xml(xml_string: str) -> str:
    """Compute a stable hash of an XML string"""
    normalized = xml_string.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def compute_hash_of_raw_data(
    raw_json: dict | None = None, raw_xml: str | None = None
) -> str:
    """
    Compute a stable hash of raw data, either JSON or XML.
    """
    if raw_json is not None and raw_xml is not None:
        raise ValueError("Only one of raw_json or raw_xml should be provided")

    if raw_json is not None:
        return compute_hash_of_json(raw_json)
    elif raw_xml is not None:
        return compute_hash_of_xml(raw_xml)
    else:
        raise ValueError("Either raw_json or raw_xml must be provided")


def store_raw_data(
    museum_slug: str,
    object_id: str,
    raw_json: dict | None = None,
    raw_xml: str | None = None,
) -> bool:
    """
    Store or update raw data in the database.
    Returns True if the data was changed (indicating a re-embedding is needed),
    """
    raw_hash = compute_hash_of_raw_data(raw_json, raw_xml)

    existing = MetaDataRaw.objects.filter(
        museum_slug=museum_slug, museum_object_id=object_id
    ).first()

    if existing and existing.raw_hash == raw_hash:
        return False  # no update needed

    MetaDataRaw.objects.update_or_create(
        museum_slug=museum_slug,
        museum_object_id=object_id,
        defaults={
            "raw_xml": raw_xml,
            "raw_json": raw_json,
            "raw_hash": raw_hash,
            "fetched_at": timezone.now(),
        },
    )
    return True  # indicates change → trigger re-embedding


def main():
    """
    Test that it works
    """
    test_items = [
        {
            "museum_slug": "test_mus",
            "museum_object_id": "test_object_123",
            "raw_json": {"key": "value2"},
        },
        {
            "museum_slug": "test_mus",
            "museum_object_id": "test_object_456",
            "raw_xml": "<root><key>another_value</key></root>",
        },
    ]
    for test_item in test_items:
        print(
            f"Storing raw data for {test_item['museum_slug']} - {test_item['museum_object_id']}"
        )
        changed = store_raw_data(
            museum_slug=test_item["museum_slug"],
            object_id=test_item["museum_object_id"],
            raw_json=test_item["raw_json"] if "raw_json" in test_item else None,
            raw_xml=test_item["raw_xml"] if "raw_xml" in test_item else None,
        )
        if changed:
            print("Data changed, re-embedding needed.")
        else:
            print("No changes detected, no re-embedding needed.")
