from typing import Optional
from etl.pipeline.transform.utils import safe_int_from_date, get_searchable_work_types
from etl.pipeline.transform.base_transformer import BaseTransformer


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
        """
        Extract work types from MET classification and objectName fields.

        NB:
            - Many MET artworks do not have a classification.
            - We include objectName to capture more work type info.
            - "classification" includes 'paintings', 'drawings', 'sculpture', 'prints',
                 'fire-arms-miniature', 'miscellaneous-paintings & portraits', 'furniture' etc.
            - "objectName" includes 'painting', 'painting, sculture', 'drawing', 'watercolor', 'salad bowl' etc.
        """
        work_types = set()
        classification = raw_json.get("classification", "").lower().strip()
        object_name = raw_json.get("objectName", "").lower().strip()

        if classification:
            work_types.add(classification)

        if object_name:
            # We split by comma since there are object names like "painting, miniature"
            object_name_parts = {part.strip() for part in object_name.split(",")}
            work_types.update(object_name_parts)

        return list(work_types)

    def extract_searchable_work_types(self, raw_json: dict) -> list[str]:
        """Extract searchable work types using current helper function."""
        # Default implementation using extracted work type and helper function.
        # We could make a version that is both museum specific and independent of the extracted work types, if needed.
        work_types = self.extract_work_types(raw_json)
        return get_searchable_work_types(work_types)

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

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
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
