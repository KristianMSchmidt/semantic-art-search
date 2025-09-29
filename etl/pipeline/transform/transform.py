from __future__ import annotations

import logging
from typing import Literal, Optional

from django.db import transaction
from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.transform.factory import get_transformer
from etl.pipeline.transform.models import TransformerArgs

logger = logging.getLogger(__name__)


def transform_and_upsert(
    metadata_raw: MetaDataRaw,
) -> Literal["created", "updated", "failed"]:
    """
    Transform a single raw data record and upsert to TransformedData table.
    Simple approach - always attempt to transform and upsert.
    """
    museum_slug = metadata_raw.museum_slug
    object_number = metadata_raw.object_number
    museum_db_id = metadata_raw.museum_db_id
    raw_json = metadata_raw.raw_json

    transformer = get_transformer(museum_slug)
    if not transformer:
        logger.warning("No transformer available for museum: %s", museum_slug)
        return "failed"

    try:
        transformer_args = TransformerArgs(
            museum_slug=museum_slug,
            object_number=object_number,
            museum_db_id=museum_db_id,
            raw_json=raw_json,
        )

        transformed = transformer(transformer_args)

        if not transformed:
            return "failed"

        transformed_dict = transformed.to_dict()

        with transaction.atomic():
            obj, created = TransformedData.objects.update_or_create(
                museum_slug=museum_slug,
                object_number=object_number,
                defaults=transformed_dict,
            )
            return "created" if created else "updated"

    except Exception as e:
        logger.exception(
            f"Transform error for {museum_slug}:{object_number}:{museum_db_id}",
            e,
        )
        return "failed"


def run_transform(batch_size: int = 1000, museum: Optional[str] = None):
    """
    Transform all raw metadata records, optionally filtered by museum.
    """
    processed = created = updated = failed = 0

    # Build queryset - all records or filtered by museum
    queryset = MetaDataRaw.objects.all()
    if museum:
        queryset = queryset.filter(museum_slug=museum)

    queryset = queryset.order_by("id")
    total_records = queryset.count()

    logger.info(
        f"Starting transform for {total_records} records (museum={museum or 'all'})"
    )

    # Process in batches
    offset = 0
    while offset < total_records:
        raw_batch = list(queryset[offset : offset + batch_size])
        if not raw_batch:
            break

        batch_created = batch_updated = batch_failed = 0

        for raw in raw_batch:
            status = transform_and_upsert(raw)
            if status == "created":
                created += 1
                batch_created += 1
            elif status == "updated":
                updated += 1
                batch_updated += 1
            elif status == "failed":
                failed += 1
                batch_failed += 1

            processed += 1

        offset += batch_size

        logger.info(
            f"Batch complete. Progress: {processed}/{total_records} "
            f"({(processed / total_records) * 100:.1f}%) - "
            f"created={batch_created}, updated={batch_updated}, failed={batch_failed}"
        )

    logger.info(
        f"Transform complete. total_processed={processed}, created={created}, updated={updated}, failed={failed})"
    )
