from typing import Optional
from etl.pipeline.transform.utils import safe_int_from_date
from etl.pipeline.transform.base_transformer import BaseTransformer


# MET classification mapping (from the API client)
MET_CLASSIFICATION_TO_WORK_TYPE = {
    "paintings": "painting",
    "miniatures": "miniature",
    "pastels": "pastel",
    "oil sketches on paper": "oil sketch on paper",
    "drawings": "drawing",
    "prints": "print",
}


class MetTransformer(BaseTransformer):
    """MET (Metropolitan Museum of Art) data transformer."""

    museum_slug = "met"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """Check if MET record should be skipped based on public domain status."""
        if not raw_json.get("isPublicDomain"):
            return True, "Not public domain"
        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """Extract thumbnail URL from MET primaryImageSmall field."""
        return raw_json.get("primaryImageSmall")

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """Extract work types from MET classification and objectName fields."""
        work_types = []
        classification = raw_json.get("classification", "").lower().strip()
        object_name = raw_json.get("objectName", "").lower().strip()

        if classification:
            # Handle multiple classifications separated by &
            classification_parts = [part.strip() for part in classification.split("&")]
            for part in classification_parts:
                if part in MET_CLASSIFICATION_TO_WORK_TYPE:
                    work_types.append(MET_CLASSIFICATION_TO_WORK_TYPE[part])
        elif object_name:
            # Use object name directly if no classification
            work_types = [object_name]

        return work_types

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract title from MET title field."""
        return raw_json.get("title")

    def extract_artists(self, raw_json: dict) -> list[str]:
        """Extract artist names from MET constituents or artistDisplayName."""
        artist = []

        # Prefer constituents
        constituents = raw_json.get("constituents", [])
        if constituents:
            artist = [
                constituent.get("name", "")
                for constituent in constituents
                if constituent.get("name")
            ]

        # Fallback to artistDisplayName if no constituents
        if not artist:
            artist_display_name = raw_json.get("artistDisplayName")
            if artist_display_name:
                artist = [artist_display_name]

        return artist

    def extract_production_dates(self, raw_json: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract production dates from MET objectBeginDate and objectEndDate."""
        production_date_start = None
        production_date_end = None

        begin_date = raw_json.get("objectBeginDate")
        end_date = raw_json.get("objectEndDate")

        if begin_date:
            production_date_start = safe_int_from_date(str(begin_date))
        if end_date:
            production_date_end = safe_int_from_date(str(end_date))

        return production_date_start, production_date_end

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period from MET period field, fallback to objectDate."""
        period = raw_json.get("period")
        if not period:
            period = raw_json.get("objectDate")
        return period

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract full resolution image URL from MET primaryImage field."""
        return raw_json.get("primaryImage")


