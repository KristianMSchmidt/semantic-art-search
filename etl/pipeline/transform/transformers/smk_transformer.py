from typing import Optional, Any
from etl.pipeline.transform.utils import safe_int_from_date
from etl.pipeline.transform.base_transformer import BaseTransformer


class SmkTransformer(BaseTransformer):
    """SMK (Statens Museum for Kunst) data transformer."""

    museum_slug = "smk"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """SMK doesn't need to skip records based on rights - all data is accessible."""
        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """Extract thumbnail URL from SMK data."""
        return raw_json.get("image_thumbnail")

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """Extract work types from SMK object_names."""
        work_types = []
        object_names = raw_json.get("object_names", [])
        if object_names:
            work_types = [
                obj_name.get("name", "").lower()
                for obj_name in object_names
                if obj_name.get("name")
            ]
        return work_types

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract primary title from SMK titles array."""
        titles = raw_json.get("titles", [])
        return extract_primary_title(titles)

    def extract_artists(self, raw_json: dict) -> list[str]:
        """Extract artist names from SMK artist array."""
        artists_raw = raw_json.get("artist", [])
        return extract_artist_names(artists_raw)

    def extract_production_dates(self, raw_json: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract production date range from SMK production_date array."""
        production_dates = raw_json.get("production_date", [])

        if production_dates and len(production_dates) > 0:
            date_obj = production_dates[0]
            if isinstance(date_obj, dict):
                start_date = date_obj.get("start")
                end_date = date_obj.get("end")

                production_date_start = None
                production_date_end = None

                if start_date:
                    production_date_start = safe_int_from_date(start_date)
                if end_date:
                    production_date_end = safe_int_from_date(end_date)

                return production_date_start, production_date_end

        return None, None

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period from SMK production_date."""
        production_dates = raw_json.get("production_date", [])

        if production_dates and len(production_dates) > 0:
            date_obj = production_dates[0]
            if isinstance(date_obj, dict):
                return date_obj.get("period")

        return None

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract full resolution image URL from SMK IIIF ID."""
        return raw_json.get("image_iiif_id")




### Utils and helpers specific to SMK transformation ###


def extract_primary_title(titles: list[dict]) -> str | None:
    """
    Extract the primary title from various title structures.

    Handles SMK-style title lists with language/type specifications.
    """
    if not titles or not isinstance(titles, list):
        return None

    # Try to find primary title (usually first one or one marked as primary)
    for title_obj in titles:
        if isinstance(title_obj, dict):
            # SMK format: {"title": "Title text", "language": "da", "type": "main"}
            if title_obj.get("title"):
                return title_obj["title"]
        elif isinstance(title_obj, str):
            # Simple string format
            return title_obj

    return None


def extract_artist_names(artists: list[Any]) -> list[str]:
    """
    Extract artist names from various artist data structures.

    Handles both simple strings and complex objects with name fields.
    """
    if not artists or not isinstance(artists, list):
        return []

    names = []
    for artist in artists:
        if isinstance(artist, str):
            names.append(artist)
        elif isinstance(artist, dict):
            # Try common name fields
            name = (
                artist.get("name") or artist.get("title") or artist.get("artist_name")
            )
            if name:
                names.append(name)

    return names
