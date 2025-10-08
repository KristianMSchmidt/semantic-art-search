import logging
import time
from typing import Literal, Optional
from django.db import models, transaction
from django.db.models import Q
import requests

from etl.models import TransformedData
from etl.services.bucket_service import BucketService

logger = logging.getLogger(__name__)


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.

    Retryable errors (transient):
    - Timeout errors
    - Connection errors
    - 5xx server errors (500, 502, 503, 504)
    - 429 Too Many Requests

    Non-retryable errors (permanent):
    - 404 Not Found
    - 403 Forbidden
    - 410 Gone
    - Other 4xx errors (bad request, etc.)
    - Invalid content type

    Args:
        error: The exception raised during image download

    Returns:
        True if error should be retried, False otherwise
    """
    # Timeout and connection errors - always retry
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True

    # Check for HTTP errors embedded in RuntimeError (from bucket_service)
    if isinstance(error, RuntimeError):
        error_msg = str(error).lower()

        # 5xx errors - retry
        if any(code in error_msg for code in ["500", "502", "503", "504"]):
            return True

        # 429 Rate limiting - retry
        if "429" in error_msg:
            return True

        # 4xx errors (except 429) - don't retry
        if any(code in error_msg for code in ["400", "401", "403", "404", "410"]):
            return False

        # Other RuntimeErrors (like invalid content type) - don't retry
        return False

    # Other errors - don't retry
    return False


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

    def reset_image_load_failed_field(self, museum_filter: Optional[str] = None) -> int:
        """
        Reset image_load_failed field to False for all records.
        Used to retry previously failed image downloads.

        Args:
            museum_filter: Optional museum slug to filter by

        Returns:
            Number of records updated
        """
        query = Q()

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        count = TransformedData.objects.filter(query).update(image_load_failed=False)
        logger.info(
            "Reset %d records' image_load_failed field to False (museum_filter=%s)",
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
        - image_load_failed=False (skip previously failed records)
        - if museum_filter is set, only that museum
        """
        # Only process records that haven't been loaded yet and haven't failed
        query = Q(image_loaded=False, image_load_failed=False)

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).order_by("id")[:batch_size]

    def process_single_record(
        self,
        record: TransformedData,
        delay_seconds: float = 0.0,
        max_retries: int = 3,
    ) -> Literal["success", "error"]:
        """
        Process a single TransformedData record for image loading with retry logic.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit API calls
            max_retries: Maximum number of retry attempts for transient errors

        Returns status of the operation.
        """
        logger.info(f"Processing {record.museum_slug}:{record.object_number}")

        last_error = None
        for attempt in range(max_retries):
            try:
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
                last_error = e

                # Check if error is retryable
                if not is_retryable_error(e):
                    # Permanent error - don't retry
                    logger.error(
                        f"Permanent error processing {record.museum_slug}:{record.object_number}: {e}"
                    )
                    break

                # Transient error - retry with exponential backoff
                if attempt < max_retries - 1:
                    retry_delay = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"Transient error processing {record.museum_slug}:{record.object_number} "
                        f"(attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    # All retries exhausted
                    logger.error(
                        f"All {max_retries} retries exhausted for {record.museum_slug}:{record.object_number}: {e}"
                    )

        # If we get here, all attempts failed
        logger.exception(
            f"Failed to process {record.museum_slug}:{record.object_number}: {last_error}"
        )

        # Mark as failed to prevent infinite retry loops
        with transaction.atomic():
            record.image_load_failed = True
            record.save(update_fields=["image_load_failed"])

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
