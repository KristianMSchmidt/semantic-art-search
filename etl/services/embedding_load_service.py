import logging
import time
from typing import Literal, Optional, Dict, List
from django.db import models, transaction
from django.db.models import Q
from qdrant_client.http.models import PointStruct, VectorParams, Distance
import requests

from etl.models import TransformedData
from etl.services.bucket_service import get_bucket_image_url
from etl.utils import generate_uuid5
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.qdrant_service import QdrantService
from artsearch.src.config import config

logger = logging.getLogger(__name__)


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.

    Retryable errors (transient):
    - Timeout errors
    - Connection errors
    - 5xx server errors (500, 502, 503, 504)
    - 429 Too Many Requests
    - Qdrant connection/timeout errors

    Non-retryable errors (permanent):
    - 404 Not Found (image missing from bucket)
    - 403 Forbidden
    - 410 Gone
    - Other 4xx errors (bad request, etc.)
    - Invalid image format/corrupted image
    - CLIP model errors (e.g., invalid tensor size)

    Args:
        error: The exception raised during embedding generation

    Returns:
        True if error should be retried, False otherwise
    """
    # Timeout and connection errors - always retry
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True

    # Check for HTTP errors embedded in RuntimeError or ValueError
    if isinstance(error, (RuntimeError, ValueError)):
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

        # Image/CLIP-specific errors - don't retry
        if any(
            phrase in error_msg
            for phrase in [
                "invalid image",
                "corrupted",
                "cannot identify image",
                "truncated",
                "tensor",
            ]
        ):
            return False

        # Qdrant connection errors - retry
        if any(phrase in error_msg for phrase in ["qdrant", "connection", "timeout"]):
            return True

        # Other errors - don't retry by default
        return False

    # PIL/Image errors - don't retry
    if error.__class__.__name__ in ["UnidentifiedImageError", "OSError", "IOError"]:
        return False

    # Other errors - don't retry
    return False


# Active vector types configuration - easy to expand later
ACTIVE_VECTOR_TYPES = ["image_clip", "image_jina"]

# Vector type to database field mapping
VECTOR_TYPE_TO_FIELD = {
    "image_clip": "image_vector_clip",
    "text_clip": "text_vector_clip",
    "image_jina": "image_vector_jina",
    "text_jina": "text_vector_jina",
}


class EmbeddingLoadService:
    """
    Service for generating CLIP image embeddings and uploading to Qdrant.

    Simplified version that uses only the boolean vector fields for tracking.
    No hash-based change detection - keeps things simple.

    Features:
    - Only processes records where image_loaded=True
    - CLIP image embedding generation from E0 bucket (our own storage)
    - Qdrant collection creation with 4 named vectors
    - Active vector type system for incremental activation
    - Progress tracking using boolean fields (image_vector_clip, etc.)
    - Batch processing for efficiency
    - Optional rate limiting for controlled resource usage
    - Natural pagination prevents infinite loops (management command loop)
    """

    def __init__(
        self,
        collection_name: str | None = None,
        clip_embedder=None,
        qdrant_service=None,
    ):
        self.collection_name = collection_name or config.qdrant_collection_name_etl
        self.clip_embedder = clip_embedder or get_clip_embedder()
        self.qdrant_service = qdrant_service or QdrantService(
            collection_name=self.collection_name
        )
        self._ensure_collection_exists()

    def reset_vector_fields(self, museum_filter: Optional[str] = None) -> int:
        """
        Reset all active vector fields to False for records.
        Used for force reload to recalculate all active vectors.

        Args:
            museum_filter: Optional museum slug to filter by

        Returns:
            Number of records updated
        """
        query = Q()

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        # Build update dict for all active vector fields
        update_fields = {}
        for vector_type in ACTIVE_VECTOR_TYPES:
            field_name = VECTOR_TYPE_TO_FIELD[vector_type]
            update_fields[field_name] = False

        count = TransformedData.objects.filter(query).update(**update_fields)
        logger.info(
            "Reset %d records' active vector fields to False (museum_filter=%s)",
            count,
            museum_filter,
        )
        return count

    def reset_embedding_load_failed_field(
        self, museum_filter: Optional[str] = None
    ) -> int:
        """
        Reset embedding_load_failed field to False for all records.
        Used to retry previously failed embedding generations.

        Args:
            museum_filter: Optional museum slug to filter by

        Returns:
            Number of records updated
        """
        query = Q()

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        count = TransformedData.objects.filter(query).update(
            embedding_load_failed=False
        )
        logger.info(
            "Reset %d records' embedding_load_failed field to False (museum_filter=%s)",
            count,
            museum_filter,
        )
        return count

    def _ensure_collection_exists(self):
        """Create Qdrant collection with 4 named vectors if it doesn't exist."""
        try:
            if not self.qdrant_service.qdrant_client.collection_exists(
                self.collection_name
            ):
                logger.info(f"Creating Qdrant collection: {self.collection_name}")

                # Create collection with 4 named vectors
                vectors_config = {
                    "text_clip": VectorParams(size=768, distance=Distance.COSINE),
                    "image_clip": VectorParams(size=768, distance=Distance.COSINE),
                    "text_jina": VectorParams(size=256, distance=Distance.COSINE),
                    "image_jina": VectorParams(size=256, distance=Distance.COSINE),
                }

                self.qdrant_service.qdrant_client.create_collection(
                    collection_name=self.collection_name, vectors_config=vectors_config
                )
                logger.info(
                    "Successfully created collection %s with 4 named vectors",
                    self.collection_name,
                )
            else:
                logger.info(f"Collection {self.collection_name} already exists")
        except Exception as e:
            logger.error(f"Failed to create/verify Qdrant collection: {e}")
            raise

    def get_records_needing_processing(
        self,
        batch_size: int = 1000,
        museum_filter: Optional[str] = None,
    ) -> models.QuerySet[TransformedData]:
        """
        Get TransformedData records that need embedding processing.

        Args:
            batch_size: Maximum number of records to return
            museum_filter: Optional museum slug to filter by

        Returns records where:
        - image_loaded=True (prerequisite - images must be in bucket)
        - embedding_load_failed=False (skip previously failed records)
        - At least ONE active vector is missing (False)
        - if museum_filter is set, only that museum
        """
        # Prerequisite: image must be loaded to bucket and not previously failed
        query = Q(image_loaded=True, embedding_load_failed=False)

        # Only get records where at least one active vector is missing
        vector_query = Q()
        for vector_type in ACTIVE_VECTOR_TYPES:
            field_name = VECTOR_TYPE_TO_FIELD[vector_type]
            vector_query |= Q(**{field_name: False})
        query &= vector_query

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).order_by("id")[:batch_size]

    def _create_qdrant_point(
        self, record: TransformedData, vectors_dict: Dict[str, List[float]]
    ) -> PointStruct:
        """
        Create a Qdrant point with 4 named vectors and metadata payload.

        Args:
            record: The database record
            vectors_dict: Dict of calculated vectors (only active types)

        Active vector types use calculated values, non-active types use zero vectors.
        This allows incremental activation of new vector types in the future.

        For existing points with vectors already stored, fetches and preserves those
        vectors to avoid overwriting them when adding new vector types.
        """
        point_id = generate_uuid5(record.museum_slug, record.object_number)

        # Default zero vectors for all types
        all_vectors: Dict[str, List[float]] = {
            "text_clip": [0.0] * 768,
            "image_clip": [0.0] * 768,
            "text_jina": [0.0] * 256,
            "image_jina": [0.0] * 256,
        }

        # Only fetch existing vectors if point likely exists (any vector flag is True)
        # This avoids unnecessary Qdrant calls for new records
        point_likely_exists = any(
            getattr(record, VECTOR_TYPE_TO_FIELD[vt]) for vt in VECTOR_TYPE_TO_FIELD
        )
        if point_likely_exists:
            existing_vectors = self.qdrant_service.get_point_vectors(point_id)
            if existing_vectors:
                all_vectors.update(existing_vectors)

        # Update with newly calculated vectors
        all_vectors.update(vectors_dict)

        # Create named vectors dict
        vectors: Dict[str, List[float]] = all_vectors

        # Create metadata payload
        payload = {
            "museum": record.museum_slug,
            "object_number": record.object_number,
            "museum_db_id": record.museum_db_id,
            "title": record.get_primary_title(),
            "artists": record.artists,
            "production_date": record.get_period(),
            "work_types": record.work_types,
            "searchable_work_types": record.searchable_work_types,
        }

        return PointStruct(
            id=point_id,
            vector=vectors,  # type: ignore
            payload=payload,
        )

    def _calculate_vector(
        self, vector_type: str, record: TransformedData
    ) -> List[float]:
        """
        Calculate a specific vector type for a record.

        Args:
            vector_type: Type of vector to calculate (image_clip, text_clip, etc.)
            record: The database record

        Returns:
            Calculated vector as list of floats

        Raises:
            NotImplementedError: If vector type calculation is not yet implemented
        """
        if vector_type == "image_clip":
            # Get image URL from ETL bucket
            bucket_url = get_bucket_image_url(
                record.museum_slug, record.object_number, use_etl_bucket=True
            )
            embedding = self.clip_embedder.generate_thumbnail_embedding(
                thumbnail_url=bucket_url, object_number=record.object_number
            )
            if embedding is None:
                raise ValueError(f"Failed to generate {vector_type} embedding")
            return embedding

        elif vector_type == "text_clip":
            raise NotImplementedError(
                "text_clip vector calculation not yet implemented"
            )

        elif vector_type == "image_jina":
            from artsearch.src.services.jina_embedder import get_jina_embedder

            bucket_url = get_bucket_image_url(
                record.museum_slug, record.object_number, use_etl_bucket=True
            )
            jina_embedder = get_jina_embedder()
            embedding = jina_embedder.generate_image_embedding(bucket_url)
            return embedding

        elif vector_type == "text_jina":
            raise NotImplementedError(
                "text_jina vector calculation not yet implemented"
            )

        else:
            raise ValueError(f"Unknown vector type: {vector_type}")

    def process_single_record(
        self,
        record: TransformedData,
        delay_seconds: float = 0.0,
        max_retries: int = 3,
    ) -> Literal["success", "error"]:
        """
        Process a single TransformedData record for embedding generation with retry logic.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit
            max_retries: Maximum number of retry attempts for transient errors

        Returns status of the operation.
        """
        logger.info("Processing %s:%s", record.museum_slug, record.object_number)

        last_error = None
        for attempt in range(max_retries):
            try:
                # Determine which active vectors need to be calculated
                vectors_to_calculate = []
                for vector_type in ACTIVE_VECTOR_TYPES:
                    field_name = VECTOR_TYPE_TO_FIELD[vector_type]
                    already_calculated = getattr(record, field_name)

                    if not already_calculated:
                        vectors_to_calculate.append(vector_type)

                # If nothing to calculate, skip this record
                if not vectors_to_calculate:
                    logger.debug(
                        "Skipping %s:%s - all active vectors already calculated",
                        record.museum_slug,
                        record.object_number,
                    )
                    return "success"

                logger.info(
                    "Calculating vectors for %s:%s: %s",
                    record.museum_slug,
                    record.object_number,
                    vectors_to_calculate,
                )

                # Calculate needed vectors
                calculated_vectors: Dict[str, List[float]] = {}
                for vector_type in vectors_to_calculate:
                    calculated_vectors[vector_type] = self._calculate_vector(
                        vector_type, record
                    )

                # Create Qdrant point with calculated vectors
                point = self._create_qdrant_point(record, calculated_vectors)

                # Upload to Qdrant
                self.qdrant_service.upload_points([point])

                # Update record status for calculated vector types
                with transaction.atomic():
                    update_fields = []
                    for vector_type in vectors_to_calculate:
                        field_name = VECTOR_TYPE_TO_FIELD[vector_type]
                        setattr(record, field_name, True)
                        update_fields.append(field_name)

                    record.save(update_fields=update_fields)

                logger.info(
                    "Successfully processed %s:%s",
                    record.museum_slug,
                    record.object_number,
                )

                # Optional delay for controlled processing rate
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
                    retry_delay = 2**attempt  # 1s, 2s, 4s
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
            record.embedding_load_failed = True
            record.save(update_fields=["embedding_load_failed"])

        return "error"

    def run_batch_processing(
        self,
        batch_size: int = 1000,
        museum_filter: Optional[str] = None,
        delay_seconds: float = 0.0,
        batch_delay_seconds: int = 0,
    ) -> dict[str, int]:
        """
        Run batch processing of embedding generation and upload.

        Args:
            batch_size: Number of records to process in this batch
            museum_filter: Optional museum slug to filter by
            delay_seconds: Delay in seconds between individual embedding generations
            batch_delay_seconds: Delay in seconds after completing the batch

        Returns:
            Dictionary with counts: {"success": int, "error": int, "total": int}
        """
        logger.info(
            "Starting embedding processing batch (batch_size=%d, museum_filter=%s, delay=%s, batch_delay=%s)",
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

            if i % 10 == 0:
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

        # Optional batch delay for controlled processing rate
        if batch_delay_seconds > 0:
            logger.info(
                "Batch delay: waiting %d seconds before next batch", batch_delay_seconds
            )
            time.sleep(batch_delay_seconds)

        return stats
