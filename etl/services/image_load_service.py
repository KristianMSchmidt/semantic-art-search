import logging
import time
from typing import Literal, Optional
from django.db import models, transaction
from django.db.models import Q

from etl.models import TransformedData
from etl.services.bucket_service import BucketService

logger = logging.getLogger(__name__)


class ImageLoadService:
    """
    Service for loading thumbnail images from museum URLs to S3 bucket.

    Simplified version that uses only the image_loaded boolean field for tracking.
    No hash-based change detection - keeps things simple.

    Features:
    - Process records where image_loaded=False
    - Batch processing for efficiency
    - Rate limiting to be polite to museum APIs
    - Natural pagination prevents infinite loops (management command loop)
    """

    def __init__(self, bucket_service: Optional[BucketService] = None):
        self.bucket_service = bucket_service or BucketService()

    def reset_image_loaded_field(self, museum_filter: Optional[str] = None) -> int:
        """
        Reset image_loaded field to False for all records.
        Used for force reload to re-download all images.

        Args:
            museum_filter: Optional museum slug to filter by

        Returns:
            Number of records updated
        """
        query = Q()

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        count = TransformedData.objects.filter(query).update(image_loaded=False)
        logger.info(
            "Reset %d records' image_loaded field to False (museum_filter=%s)",
            count,
            museum_filter,
        )
        return count

    def get_records_needing_processing(
        self,
        batch_size: int = 1000,
        museum_filter: Optional[str] = None,
    ) -> models.QuerySet[TransformedData]:
        """
        Get TransformedData records that need image processing.

        Args:
            batch_size: Maximum number of records to return
            museum_filter: Optional museum slug to filter by

        Returns records where:
        - image_loaded=False
        - if museum_filter is set, only that museum
        """
        # Only process records that haven't been loaded yet
        query = Q(image_loaded=False)

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).order_by("id")[:batch_size]

    def process_single_record(
        self,
        record: TransformedData,
        delay_seconds: float = 0.0,
    ) -> Literal["success", "error"]:
        """
        Process a single TransformedData record for image loading.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit API calls

        Returns status of the operation.
        """
        try:
            logger.info(
                f"Processing {record.museum_slug}:{record.object_number}"
            )

            # Download and upload image
            self.bucket_service.upload_thumbnail(
                museum=record.museum_slug,
                object_number=record.object_number,
                museum_image_url=record.thumbnail_url,
            )

            # Update record status
            with transaction.atomic():
                record.image_loaded = True
                record.save(update_fields=["image_loaded"])

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
            batch_size: Number of records to process in this batch
            museum_filter: Optional museum slug to filter by
            delay_seconds: Delay in seconds between individual image downloads
            batch_delay_seconds: Delay in seconds after completing the batch

        Returns:
            Dictionary with counts: {"success": int, "error": int, "total": int}
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
            return {"success": 0, "error": 0, "total": 0}

        logger.info("Found %d records to process", record_count)

        # Process each record
        stats = {"success": 0, "error": 0}

        for i, record in enumerate(records, 1):
            status = self.process_single_record(record, delay_seconds)
            stats[status] += 1

            if i % 100 == 0:
                logger.info(
                    "Progress: %d/%d processed (success=%d, error=%d)",
                    i,
                    record_count,
                    stats["success"],
                    stats["error"],
                )

        stats["total"] = record_count
        logger.info(
            "Batch complete: processed %d records (success=%d, error=%d)",
            record_count,
            stats["success"],
            stats["error"],
        )

        # Batch delay to be respectful to museum APIs
        if batch_delay_seconds > 0:
            logger.info(
                "Batch delay: waiting %d seconds before next batch", batch_delay_seconds
            )
            time.sleep(batch_delay_seconds)

        return stats
