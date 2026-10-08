from typing import Optional
from etl.pipeline.transform.base_transformer import BaseTransformer
from etl.pipeline.transform.utils import get_searchable_work_types

# Must cover ALLOWED_CLASSIFICATIONS in nga_extractor.py (may include more, for later use)
CLASSIFICATION_TO_WORK_TYPE = {
    "Painting": "painting",
    "Drawing": "drawing",
    "Print": "print",
    # Index of American Design: watercolor/graphite renderings, classified by NGA as drawings
    "Index of American Design": "drawing",
}

# Medium keywords that add a more specific work type, per base work type.
# E.g. "watercolor, graphite, and gouache on paper" -> drawing + watercolor + gouache
MEDIUM_WORK_TYPES = {
    "drawing": ["watercolor", "pastel", "gouache"],
    "print": ["aquatint"],
}

MAX_TITLE_LENGTH = 500  # TransformedData.title max_length


class NgaTransformer(BaseTransformer):
    """NGA (National Gallery of Art, Washington) data transformer."""

    museum_slug = "nga"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """Check if NGA record should be skipped based on open access status."""
        # Defensive check - should already be filtered in extraction
        if raw_json.get("image", {}).get("openaccess") != "1":
            return True, "Image not open access"
        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """
        Extract thumbnail URL using NGA's IIIF Image API (v2).

        '!800,800' scales the image to fit within 800x800, maintaining aspect ratio.
        """
        iiif_url = raw_json.get("image", {}).get("iiifurl")
        if not iiif_url:
            return None
        return f"{iiif_url}/full/!800,800/0/default.jpg"

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """
        Extract work types from NGA classification, subclassification and medium.

        NGA provides:
        - classification: "Painting", "Drawing", "Print", "Index of American Design"
        - subclassification: often empty, sometimes more specific (e.g. "Miniature")
        - medium: free text, e.g. "etching and aquatint", "watercolor and graphite on paper"
        """
        classification = raw_json.get("classification", "")
        work_type = CLASSIFICATION_TO_WORK_TYPE.get(classification)
        if work_type is None:
            raise ValueError(
                f"Unexpected NGA classification: '{classification}'. "
                f"This should have been filtered during extraction. "
                f"Check that ALLOWED_CLASSIFICATIONS in nga_extractor.py matches CLASSIFICATION_TO_WORK_TYPE."
            )

        work_types = [work_type]

        if raw_json.get("subclassification", "").lower() == "miniature":
            work_types.append("miniature")

        medium = raw_json.get("medium", "").lower()
        for keyword in MEDIUM_WORK_TYPES.get(work_type, []):
            if keyword in medium:
                work_types.append(keyword)

        return work_types

    def extract_searchable_work_types(self, raw_json: dict) -> list[str]:
        """Extract searchable work types using current helper function."""
        work_types = self.extract_work_types(raw_json)
        return get_searchable_work_types(work_types)

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract title, truncated to fit the database field (a few NGA titles are longer)."""
        title = raw_json.get("title", "").strip()
        if not title:
            return None
        return title[:MAX_TITLE_LENGTH]

    def extract_artists(self, raw_json: dict) -> list[str]:
        """
        Extract artist from NGA attribution field.

        The attribution is NGA's display string for the artist(s), e.g. "Hans Baldung",
        "Circle of Rogier van der Weyden" or "Robert Havell after John James Audubon".
        It is kept as a single entry, since splitting it would lose the relationships.
        """
        attribution = raw_json.get("attribution", "").strip()
        return [attribution] if attribution else []

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """Extract production dates from NGA beginyear and endyear (integer strings in the CSV)."""

        def to_int(value: Optional[str]) -> Optional[int]:
            try:
                return int(value) if value else None
            except ValueError:
                return None

        return to_int(raw_json.get("beginyear")), to_int(raw_json.get("endyear"))

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period from NGA displaydate, e.g. "c. 1310", "1796-1797"."""
        return raw_json.get("displaydate", "").strip() or None

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract full resolution image URL using NGA's IIIF Image API (v2)."""
        iiif_url = raw_json.get("image", {}).get("iiifurl")
        if not iiif_url:
            return None
        return f"{iiif_url}/full/full/0/default.jpg"
