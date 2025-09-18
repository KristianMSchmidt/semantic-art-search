import hashlib
import logging
import time
from typing import Literal, Optional, Dict, List
from django.db import models, transaction
from django.db.models import Q
from qdrant_client.http.models import PointStruct, VectorParams, Distance

from etl.models import TransformedData
from artsearch.src.services.clip_embedder import get_clip_embedder
from artsearch.src.services.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)


class EmbeddingLoadService:
    """
    Service for generating CLIP image embeddings and uploading to Qdrant.

    Features:
    - CLIP image embedding generation from thumbnail URLs
    - Qdrant collection creation with 4 named vectors (future-proofed)
    - Progress tracking using image_vector_clip boolean field
    - Staleness detection for re-processing changed data
    - Batch processing for efficiency
    """

    def __init__(self, collection_name: str = "artworks_etl_v1"):
        self.collection_name = collection_name
        self.clip_embedder = get_clip_embedder()
        self.qdrant_service = get_qdrant_service()
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Create Qdrant collection with 4 named vectors if it doesn't exist."""
        try:
            # Check if collection exists
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
        force: bool = False,
    ) -> models.QuerySet[TransformedData]:
        """
        Get TransformedData records that need embedding processing.

        Args:
            force: If True, process all records regardless of processing status

        Returns records where:
        - force=True: all records, OR
        - image_vector_clip=False (never processed)
        """
        if force:
            query = Q()  # All records
        else:
            query = Q(image_vector_clip=False)

        if museum_filter:
            query &= Q(museum_slug=museum_filter)

        return TransformedData.objects.filter(query).select_related("raw_data")[
            :batch_size
        ]

    def should_process_embedding(self, record: TransformedData) -> tuple[bool, str]:
        """
        Determine if an embedding should be processed based on:
        1. Never been processed (image_vector_clip=False)
        2. Thumbnail URL changes (needs re-embedding)

        Returns:
            (should_process: bool, reason: str)
        """
        # Never processed
        if not record.image_vector_clip:
            return True, "never processed (image_vector_clip=False)"

        # Check thumbnail URL hash for re-embedding
        current_thumbnail_hash = hashlib.sha256(
            record.thumbnail_url.encode()
        ).hexdigest()
        if record.thumbnail_url_hash != current_thumbnail_hash:
            return True, "thumbnail_changed (thumbnail_url_hash mismatch)"

        return False, "already processed and up-to-date"

    def _create_qdrant_point(
        self, record: TransformedData, image_embedding: List[float]
    ) -> PointStruct:
        """
        Create a Qdrant point with 4 named vectors and metadata payload.

        Initial implementation:
        - image_clip: actual CLIP embedding
        - text_clip, text_jina, image_jina: zero vectors (placeholders)
        """
        # Create zero vectors for unused types
        text_clip_zeros = [0.0] * 768
        text_jina_zeros = [0.0] * 256
        image_jina_zeros = [0.0] * 256

        # Create named vectors dict
        vectors: Dict[str, List[float]] = {
            "text_clip": text_clip_zeros,
            "image_clip": image_embedding,
            "text_jina": text_jina_zeros,
            "image_jina": image_jina_zeros,
        }

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
            id=record.pk,
            vector=vectors,  # type: ignore
            payload=payload,
        )

    def process_single_record(
        self, record: TransformedData, delay_seconds: float = 0.0
    ) -> Literal["success", "skipped", "error"]:
        """
        Process a single TransformedData record for embedding generation.

        Args:
            record: The TransformedData record to process
            delay_seconds: Delay in seconds after processing to rate limit API calls

        Returns status of the operation.
        """
        try:
            should_process, reason = self.should_process_embedding(record)

            if not should_process:
                logger.debug(
                    "Skipping %s:%s - %s",
                    record.museum_slug,
                    record.object_number,
                    reason,
                )
                return "skipped"

            logger.info(
                "Processing %s:%s - %s",
                record.museum_slug,
                record.object_number,
                reason,
            )

            # Generate CLIP image embedding
            image_embedding = self.clip_embedder.generate_thumbnail_embedding(
                thumbnail_url=record.thumbnail_url, object_number=record.object_number
            )

            if image_embedding is None:
                logger.error(
                    "Failed to generate embedding for %s:%s",
                    record.museum_slug,
                    record.object_number,
                )
                return "error"

            # Create Qdrant point
            point = self._create_qdrant_point(record, image_embedding)

            # Upload to Qdrant
            self.qdrant_service.upload_points([point], self.collection_name)

            # Update record status and thumbnail hash
            with transaction.atomic():
                record.image_vector_clip = True
                record.thumbnail_url_hash = hashlib.sha256(
                    record.thumbnail_url.encode()
                ).hexdigest()
                record.save(update_fields=["image_vector_clip", "thumbnail_url_hash"])

            logger.info(
                "Successfully processed %s:%s", record.museum_slug, record.object_number
            )

            # Rate limiting delay to be respectful to museum APIs
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
        force: bool = False,
        delay_seconds: float = 0.0,
        batch_delay_seconds: int = 0,
    ) -> dict[str, int]:
        """
        Run batch processing of embedding generation and upload.

        Args:
            delay_seconds: Delay in seconds between individual embedding generations
            batch_delay_seconds: Delay in seconds after completing the batch

        Returns:
            Dictionary with counts: {"success": int, "skipped": int, "error": int, "total": int}
        """
        logger.info(
            "Starting embedding processing batch (batch_size=%d, museum_filter=%s, force=%s, delay=%s, batch_delay=%s)",
            batch_size,
            museum_filter,
            force,
            delay_seconds,
            batch_delay_seconds,
        )

        records = self.get_records_needing_processing(batch_size, museum_filter, force)

        stats = {"success": 0, "skipped": 0, "error": 0, "total": 0}

        for record in records:
            stats["total"] += 1
            result = self.process_single_record(record, delay_seconds)
            stats[result] += 1

            if stats["total"] % 10 == 0:
                logger.info(
                    "Progress: %d/%d processed (success: %d, skipped: %d, error: %d)",
                    stats["total"],
                    len(records),
                    stats["success"],
                    stats["skipped"],
                    stats["error"],
                )

        logger.info(
            "Batch complete: %d total, %d success, %d skipped, %d error",
            stats["total"],
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
