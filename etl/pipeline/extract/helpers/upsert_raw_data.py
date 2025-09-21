from typing import Optional
from etl.models import MetaDataRaw


def store_raw_data(
    museum_slug: str,
    object_number: str,
    raw_json: dict,
    museum_db_id: Optional[str] = None,
) -> bool:
    """
    Store or update raw data in the database.
    Returns True if a new record was created, False if updated.
    """

    obj, created = MetaDataRaw.objects.update_or_create(
        museum_slug=museum_slug,
        object_number=object_number,
        defaults={
            "museum_db_id": museum_db_id,
            "raw_json": raw_json,
        },
    )
    return created
