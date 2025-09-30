import hashlib
import logging
import time
from typing import Literal, Optional
from django.db import models, transaction
from django.db.models import Q

from etl.models import TransformedData
from artsearch.src.services.bucket_service import BucketService, get_bucket_image_key

logger = logging.getLogger(__name__)


class ImageLoadService:
    """
    Service for loading thumbnail images from museum URLs to S3 bucket.

    Features:
    - S3 existence checking to avoid redundant uploads
    - Thumbnail URL hash tracking for change detection
    - Staleness detection for re-processing changed data
    - Batch processing for efficiency
    """

    def __init__(self, bucket_service: Optional[BucketService] = None):
        self.bucket_service = bucket_service or BucketService()

    def get_records_needing_processing(
        self, batch_size: int = 1000, museum_filter: Optional[str] = None
    ) -> models.QuerySet[TransformedData]:
        """
        Get TransformedData records that need image processing.

        Returns records where:
        - image_loaded=False (never processed), OR
        - is_stale=True (raw data changed since last transform)
        """
        query = Q(image_loaded=False) | ~Q(
            source_raw_hash=models.F("raw_data__raw_hash")
        )

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).select_related("raw_data")[
            :batch_size
        ]

    def should_process_image(self, record: TransformedData) -> tuple[bool, str]:
        """
        Determine if an image should be processed based on:
        1. Hash changes (thumbnail URL changed)
        2. S3 existence (image missing from bucket)

        Returns:
            (should_process: bool, reason: str)
        """
        # Calculate current thumbnail URL hash
        current_hash = hashlib.sha256(record.thumbnail_url.encode()).hexdigest()

        # If hash changed, always process
        if record.thumbnail_url_hash != current_hash:
            return (
                True,
                f"thumbnail_url_hash changed (old: {record.thumbnail_url_hash}, new: {current_hash})",
            )

        # If hash same, check S3 existence
        s3_key = get_bucket_image_key(record.museum_slug, record.object_number)
        if not self.bucket_service.object_exists(s3_key):
            return True, f"image missing from S3 bucket (key: {s3_key})"

        return False, "image exists and hash unchanged"

    def process_single_record(
        self, record: TransformedData, delay_seconds: float = 0.0
    ) -> Literal["success", "skipped", "error"]:
        """
        Process a single TransformedData record for image loading.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit API calls

        Returns status of the operation.
        """
        try:
            should_process, reason = self.should_process_image(record)

            if not should_process:
                logger.debug(
                    f"Skipping {record.museum_slug}:{record.object_number} - {reason}"
                )
                # Still mark as loaded if it exists in S3 but wasn't marked
                if not record.image_loaded:
                    record.image_loaded = True
                    record.save(update_fields=["image_loaded"])
                return "skipped"

            logger.info(
                f"Processing {record.museum_slug}:{record.object_number} - {reason}"
            )

            # Download and upload image
            self.bucket_service.upload_thumbnail(
                museum=record.museum_slug,
                object_number=record.object_number,
                museum_image_url=record.thumbnail_url,
            )

            # Update record status and hash
            with transaction.atomic():
                record.image_loaded = True
                record.thumbnail_url_hash = hashlib.sha256(
                    record.thumbnail_url.encode()
                ).hexdigest()
                record.save(update_fields=["image_loaded", "thumbnail_url_hash"])

            logger.info(
                f"Successfully processed {record.museum_slug}:{record.object_number}"
            )

            # Rate limiting delay to be respectful to museum APIs
            if delay_seconds > 0:
                time.sleep(delay_seconds)

            return "success"

        except Exception as e:
            logger.exception(
                f"Error processing {record.museum_slug}:{record.object_number}: {e}"
            )
            return "error"

    def run_batch_processing(
        self,
        batch_size: int = 1000,
        museum_filter: Optional[str] = None,
        delay_seconds: float = 0.0,
        batch_delay_seconds: int = 0,
    ) -> dict[str, int]:
        """
        Run batch processing of image loading.

        Args:
            delay_seconds: Delay in seconds between individual image downloads
            batch_delay_seconds: Delay in seconds after completing the batch

        Returns:
            Dictionary with counts: {"success": int, "skipped": int, "error": int, "total": int}
        """
        logger.info(
            "Starting image loading batch (batch_size=%d, museum_filter=%s, delay=%s, batch_delay=%s)",
            batch_size,
            museum_filter,
            delay_seconds,
            batch_delay_seconds,
        )

        records = self.get_records_needing_processing(batch_size, museum_filter)
        record_count = len(records)

        if record_count == 0:
            logger.info("No records need processing")
            return {"success": 0, "skipped": 0, "error": 0, "total": 0}

        logger.info("Found %d records to process", record_count)

        # Process each record
        stats = {"success": 0, "skipped": 0, "error": 0}

        for i, record in enumerate(records, 1):
            status = self.process_single_record(record, delay_seconds)
            stats[status] += 1

            if i % 100 == 0:
                logger.info(
                    "Progress: %d/%d processed (success=%d, skipped=%d, error=%d)",
                    i,
                    record_count,
                    stats["success"],
                    stats["skipped"],
                    stats["error"],
                )

        stats["total"] = record_count
        logger.info(
            "Batch complete: processed %d records (success=%d, skipped=%d, error=%d)",
            record_count,
            stats["success"],
            stats["skipped"],
            stats["error"],
        )

        # Batch delay to be respectful to museum APIs
        if batch_delay_seconds > 0:
            logger.info(
                "Batch delay: waiting %d seconds before next batch", batch_delay_seconds
            )
            time.sleep(batch_delay_seconds)

        return stats
