from typing import Optional
from etl.pipeline.transform.utils import safe_int_from_date
from etl.pipeline.transform.base_transformer import BaseTransformer


class CmaTransformer(BaseTransformer):
    """CMA (Cleveland Museum of Art) data transformer."""

    museum_slug = "cma"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """CMA doesn't need to skip records based on rights - all data is accessible."""
        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """Extract thumbnail URL from CMA images.web.url."""
        try:
            return raw_json["images"]["web"]["url"]
        except (KeyError, TypeError):
            return None

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """Extract work types from CMA type field."""
        work_types = []
        work_type = raw_json.get("type")
        if work_type:
            work_types = [work_type.lower()]
        return work_types

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract title from CMA title field."""
        return raw_json.get("title")

    def extract_artists(self, raw_json: dict) -> list[str]:
        """Extract artist names from CMA creators or culture fields."""
        artist = []

        # Try creators first
        creators = raw_json.get("creators", [])
        if creators:
            artist = [
                creator.get("description", "").split("(")[0].strip()
                for creator in creators
                if creator.get("description")
            ]

        # Fallback to culture field if no creators
        if not artist:
            culture = raw_json.get("culture", [])
            if culture:
                artist = culture

        return artist

    def extract_production_dates(self, raw_json: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract production dates from CMA creation_date fields."""
        production_date_start = None
        production_date_end = None

        start_date = raw_json.get("creation_date_earliest")
        end_date = raw_json.get("creation_date_latest")

        if start_date:
            production_date_start = safe_int_from_date(start_date)
        if end_date:
            production_date_end = safe_int_from_date(end_date)

        return production_date_start, production_date_end

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period from CMA creation_date field."""
        return raw_json.get("creation_date")

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract full resolution image URL from CMA images.print.url."""
        try:
            return raw_json["images"]["print"]["url"]
        except (KeyError, TypeError):
            return None


