import logging
import time
from typing import Literal, Optional, Dict, List
from django.db import models, transaction
from django.db.models import Q
from qdrant_client.http.models import PointStruct, VectorParams, Distance

from etl.models import TransformedData
from etl.services.bucket_service import get_bucket_image_url
from etl.utils import generate_uuid5
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.qdrant_service import get_qdrant_service
from artsearch.src.config import config

logger = logging.getLogger(__name__)

# Active vector types configuration - easy to expand later
ACTIVE_VECTOR_TYPES = ["image_clip"]

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

    def __init__(self, collection_name: str | None = None):
        self.collection_name = collection_name or config.qdrant_collection_name_etl
        self.clip_embedder = get_clip_embedder()
        self.qdrant_service = get_qdrant_service()
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
        - At least ONE active vector is missing (False)
        - if museum_filter is set, only that museum
        """
        # Prerequisite: image must be loaded to bucket
        query = Q(image_loaded=True)

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
        """
        # Default zero vectors for all types
        all_vectors: Dict[str, List[float]] = {
            "text_clip": [0.0] * 768,
            "image_clip": [0.0] * 768,
            "text_jina": [0.0] * 256,
            "image_jina": [0.0] * 256,
        }

        # Update with calculated vectors
        all_vectors.update(vectors_dict)

        # Create named vectors dict
        vectors: Dict[str, List[float]] = all_vectors

        # Create metadata payload
        payload = {
            "museum": record.museum_slug,
            "object_number": record.object_number,
            "title": record.get_primary_title(),
            "artist": record.get_artists(),
            "production_date": record.get_period(),
            "work_types": record.work_types,
            "searchable_work_types": record.searchable_work_types,
        }

        return PointStruct(
            id=generate_uuid5(record.museum_slug, record.object_number),
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
            raise NotImplementedError(
                "image_jina vector calculation not yet implemented"
            )

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
    ) -> Literal["success", "error"]:
        """
        Process a single TransformedData record for embedding generation.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit

        Returns status of the operation.
        """
        try:
            logger.info("Processing %s:%s", record.museum_slug, record.object_number)

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
            self.qdrant_service.upload_points([point], self.collection_name)

            # Update record status for calculated vector types
            with transaction.atomic():
                update_fields = []
                for vector_type in vectors_to_calculate:
                    field_name = VECTOR_TYPE_TO_FIELD[vector_type]
                    setattr(record, field_name, True)
                    update_fields.append(field_name)

                record.save(update_fields=update_fields)

            logger.info(
                "Successfully processed %s:%s", record.museum_slug, record.object_number
            )

            # Optional delay for controlled processing rate
            if delay_seconds > 0:
                time.sleep(delay_seconds)

            return "success"

        except Exception as e:
            logger.exception(
                "Error processing %s:%s: %s",
                record.museum_slug,
                record.object_number,
                e,
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
