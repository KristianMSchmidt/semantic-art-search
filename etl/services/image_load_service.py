import logging
import time
from typing import Literal, Optional
from django.db import models, transaction
from django.db.models import Q

from etl.models import TransformedData
from etl.services.bucket_service import BucketService, get_bucket_image_key

logger = logging.getLogger(__name__)


class ImageLoadService:
    """
    Service for loading thumbnail images from museum URLs to S3 bucket.

    Simplified version that uses only the image_loaded boolean field for tracking.
    No hash-based change detection - keeps things simple.

    Features:
    - Process records where image_loaded=False by default
    - Force reload option to ignore image_loaded status
    - Batch processing for efficiency
    - Rate limiting to be polite to museum APIs
    - Processed record tracking to avoid infinite loops during force reload
    """

    def __init__(self, bucket_service: Optional[BucketService] = None):
        self.bucket_service = bucket_service or BucketService()
        self._processed_ids: set[int] = (
            set()
        )  # Track processed record IDs during force reload

    def reset_processed_tracking(self) -> None:
        """
        Reset the tracking of processed records.
        Should be called when starting a new force reload session.
        """
        self._processed_ids.clear()
        logger.info("Reset processed record tracking for new force reload session")

    def get_records_needing_processing(
        self,
        batch_size: int = 1000,
        museum_filter: Optional[str] = None,
        force_reload: bool = False,
    ) -> models.QuerySet[TransformedData]:
        """
        Get TransformedData records that need image processing.

        Args:
            batch_size: Maximum number of records to return
            museum_filter: Optional museum slug to filter by
            force_reload: If True, process all records regardless of image_loaded status

        Returns records where:
        - force_reload=True: All records (excluding already processed in this session)
        - force_reload=False: Only records where image_loaded=False
        """
        if force_reload:
            # Process all records when force reload is enabled, but exclude already processed ones
            query = Q()
            if self._processed_ids:
                query &= ~Q(id__in=self._processed_ids)
        else:
            # Only process records that haven't been loaded yet
            query = Q(image_loaded=False)

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).order_by("id")[:batch_size]

    def process_single_record(
        self,
        record: TransformedData,
        force_reload: bool = False,
        delay_seconds: float = 0.0,
    ) -> Literal["success", "error"]:
        """
        Process a single TransformedData record for image loading.

        Args:
            record: The TransformedData record to process
            force_reload: If True, process regardless of current image_loaded status
            delay_seconds: Delay in seconds after processing to rate limit API calls

        Returns status of the operation.

        Note: Records are pre-filtered by get_records_needing_processing(),
        so all records passed to this method should be processed.
        """
        try:
            # Track this record as processed (regardless of outcome) during force reload
            if force_reload:
                self._processed_ids.add(record.pk)

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
        force_reload: bool = False,
        delay_seconds: float = 0.0,
        batch_delay_seconds: int = 0,
    ) -> dict[str, int]:
        """
        Run batch processing of image loading.

        Args:
            batch_size: Number of records to process in this batch
            museum_filter: Optional museum slug to filter by
            force_reload: If True, process all records regardless of image_loaded status
            delay_seconds: Delay in seconds between individual image downloads
            batch_delay_seconds: Delay in seconds after completing the batch

        Returns:
            Dictionary with counts: {"success": int, "error": int, "total": int}
        """
        logger.info(
            "Starting image loading batch (batch_size=%d, museum_filter=%s, force_reload=%s, delay=%s, batch_delay=%s)",
            batch_size,
            museum_filter,
            force_reload,
            delay_seconds,
            batch_delay_seconds,
        )

        records = self.get_records_needing_processing(
            batch_size, museum_filter, force_reload
        )
        record_count = len(records)

        if record_count == 0:
            logger.info("No records need processing")
            return {"success": 0, "error": 0, "total": 0}

        logger.info("Found %d records to process", record_count)

        # Process each record
        stats = {"success": 0, "error": 0}

        for i, record in enumerate(records, 1):
            status = self.process_single_record(record, force_reload, delay_seconds)
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
