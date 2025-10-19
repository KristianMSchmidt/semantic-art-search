from abc import ABC, abstractmethod
from typing import Optional
import logging

from etl.pipeline.transform.utils import get_searchable_work_types
from etl.pipeline.transform.models import TransformedArtworkData, TransformerArgs

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """
    Abstract base class for museum data transformers.

    Provides common validation flow and error handling while requiring
    museum-specific implementations for data extraction methods.
    """

    museum_slug: str  # Must be set by subclasses

    def transform(
        self, transformer_args: TransformerArgs
    ) -> Optional[TransformedArtworkData]:
        """
        Transform raw museum metadata to TransformedArtworkData.

        Common validation flow with museum-specific extraction methods.
        Returns TransformedArtworkData instance or None if transformation fails.
        """
        try:
            # Validate museum slug
            if transformer_args.museum_slug != self.museum_slug:
                logger.error(
                    f"Transformer called for wrong museum: expected {self.museum_slug}, got {transformer_args.museum_slug}"
                )
                return None

            # Validate required args
            if not transformer_args.object_number:
                logger.debug(f"{self.museum_slug}: Missing object_number")
                return None

            if not transformer_args.museum_db_id:
                logger.debug(f"{self.museum_slug}: Missing museum_db_id")
                return None

            if not transformer_args.raw_json or not isinstance(
                transformer_args.raw_json, dict
            ):
                logger.debug(f"{self.museum_slug}: Invalid raw_json data")
                return None

            # Check if record should be skipped (museum-specific logic)
            should_skip, skip_reason = self.should_skip_record(
                transformer_args.raw_json
            )
            if should_skip:
                logger.debug(
                    f"{self.museum_slug}:{transformer_args.object_number} - Skipped: {skip_reason}"
                )
                return None

            # Extract required thumbnail_url
            thumbnail_url = self.extract_thumbnail_url(transformer_args.raw_json)
            if not thumbnail_url:
                logger.debug(
                    f"{self.museum_slug}:{transformer_args.object_number} - Missing thumbnail_url"
                )
                return None

            # Extract work types and validate
            work_types = self.extract_work_types(transformer_args.raw_json)
            searchable_work_types = get_searchable_work_types(work_types)

            if not searchable_work_types:
                logger.debug(
                    f"{self.museum_slug}:{transformer_args.object_number} - No searchable work types found, work_types={work_types}"
                )
                return None

            # Extract optional fields
            title = self.extract_title(transformer_args.raw_json)
            artist = self.extract_artists(transformer_args.raw_json)
            production_date_start, production_date_end = self.extract_production_dates(
                transformer_args.raw_json
            )
            period = self.extract_period(transformer_args.raw_json)
            image_url = self.extract_image_url(transformer_args.raw_json)

            # Create and return transformed data
            return TransformedArtworkData(
                object_number=transformer_args.object_number,
                museum_db_id=transformer_args.museum_db_id,
                title=title,
                work_types=work_types,
                searchable_work_types=searchable_work_types,
                artist=artist,
                production_date_start=production_date_start,
                production_date_end=production_date_end,
                period=period,
                thumbnail_url=str(thumbnail_url),
                museum_slug=transformer_args.museum_slug,
                image_url=image_url,
            )

        except Exception as e:
            logger.exception(
                f"{self.museum_slug} transform error for {transformer_args.object_number}:{transformer_args.museum_db_id}: {e}"
            )
            return None

    # Abstract methods for museum-specific data extraction

    @abstractmethod
    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """Extract thumbnail URL from raw JSON data."""
        pass

    @abstractmethod
    def extract_work_types(self, raw_json: dict) -> list[str]:
        """Extract work type classifications from raw JSON data."""
        pass

    @abstractmethod
    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract primary title from raw JSON data."""
        pass

    @abstractmethod
    def extract_artists(self, raw_json: dict) -> list[str]:
        """Extract artist names from raw JSON data."""
        pass

    @abstractmethod
    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """Extract production date range from raw JSON data. Returns (start_year, end_year)."""
        pass

    @abstractmethod
    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period designation from raw JSON data."""
        pass

    @abstractmethod
    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract full resolution image URL from raw JSON data."""
        pass

    @abstractmethod
    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """
        Determine if record should be skipped based on museum-specific criteria.
        Returns (should_skip: bool, reason: str).
        """
        pass
