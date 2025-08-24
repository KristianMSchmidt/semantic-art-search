from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal, Callable

from django.db import transaction
from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.transform.factory import get_transformer

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _get_transformer_cached(slug: str) -> Callable:
    return get_transformer(slug)


def transform_and_upsert(
    raw_data_obj: MetaDataRaw,
) -> Literal["created", "updated", "error", "skipped"]:
    """
    Transform a single raw data record and upsert to TransformedData table.
    Uses hash-based staleness to skip unchanged rows.
    """
    museum_slug = raw_data_obj.museum_slug
    transformer = _get_transformer_cached(museum_slug)
    if not transformer:
        logger.warning("No transformer available for museum: %s", museum_slug)
        return "error"

    try:
        # Build transformed payload (your transformer should be deterministic for a given raw_json)
        transformed = transformer(raw_data_obj.raw_json, raw_data_obj.museum_object_id)
        if not transformed:
            logger.warning(
                "Transform failed for %s:%s - invalid data",
                museum_slug,
                raw_data_obj.museum_object_id,
            )

            return "error"

        transformed_dict = transformed.to_dict()
        transformed_dict["source_raw_hash"] = raw_data_obj.raw_hash

        with transaction.atomic():
            try:
                existing = TransformedData.objects.get(raw_data=raw_data_obj)
                # Record exists - check if hash actually differs (shouldn't happen due to batch filtering)
                if existing.source_raw_hash == raw_data_obj.raw_hash:
                    return "skipped"  # shouldn't happen due to batch filtering
                else:
                    # Update existing record with new data
                    for key, value in transformed_dict.items():
                        setattr(existing, key, value)
                    existing.save()
                    return "updated"
            except TransformedData.DoesNotExist:
                # Create new record
                TransformedData.objects.create(
                    raw_data=raw_data_obj, **transformed_dict
                )
                return "created"

    except Exception as e:
        logger.exception(
            "Transform error for %s:%s: %s",
            museum_slug,
            raw_data_obj.museum_object_id,
            e,
        )
        return "error"


def run_transform(batch_size: int = 1000, start_id: int = 0):
    """
    Process raw metadata in ID order, touching only missing or stale rows.

    Strategy per batch:
      1) Fetch raw rows (id > last_id).
      2) Fetch existing transformed rows as (raw_data_id, source_raw_hash) only.
      3) For each raw row, transform+upsert if missing OR hash is stale.
    """
    last_id = start_id
    processed = skipped = errors = created = updated = 0

    while True:
        raw_batch = list(
            MetaDataRaw.objects.filter(id__gt=last_id).order_by("id")[:batch_size]
        )
        if not raw_batch:
            break

        raw_ids = [r.pk for r in raw_batch]

        # Pull only what we need from TransformedData (no JOIN, no full rows)
        existing = TransformedData.objects.filter(raw_data_id__in=raw_ids).values(
            "raw_data_id", "source_raw_hash"
        )
        hash_by_raw_id = {
            row["raw_data_id"]: row["source_raw_hash"] for row in existing
        }

        batch_proc = batch_skip = 0
        batch_created = batch_updated = batch_errors = 0

        for raw in raw_batch:
            old_hash = hash_by_raw_id.get(raw.pk)

            # Transform if missing or stale
            if old_hash is None or old_hash != raw.raw_hash:
                if old_hash is not None and old_hash != raw.raw_hash:
                    print(
                        f"Transforming stale row {raw.pk} (old_hash={old_hash}, new_hash={raw.raw_hash})"
                    )
                status = transform_and_upsert(raw)
                if status == "created":
                    created += 1
                    batch_created += 1
                    processed += 1
                    batch_proc += 1
                elif status == "updated":
                    updated += 1
                    batch_updated += 1
                    processed += 1
                    batch_proc += 1
                elif status == "error":
                    errors += 1
                    batch_errors += 1
                # keep going even on error
            else:
                skipped += 1
                batch_skip += 1

        last_id = raw_batch[-1].pk
        logger.info(
            "Batch complete. processed=%d (created=%d, updated=%d) skipped=%d errors=%d last_id=%d",
            batch_proc,
            batch_created,
            batch_updated,
            batch_skip,
            batch_errors,
            last_id,
        )

    logger.info(
        "Transform complete. total_processed=%d (created=%d, updated=%d) total_skipped=%d errors=%d",
        processed,
        created,
        updated,
        skipped,
        errors,
    )
