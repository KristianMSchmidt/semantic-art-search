from typing import Optional
from etl.pipeline.transform.base_transformer import BaseTransformer


class AicTransformer(BaseTransformer):
    """AIC (Art Institute of Chicago) data transformer."""

    museum_slug = "aic"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """Check if AIC record should be skipped based on public domain status."""
        # Defensive check - should already be filtered in extraction
        if not raw_json.get("is_public_domain"):
            return True, "Not public domain"
        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """
        Extract thumbnail URL from AIC image_id using IIIF API.

        AIC provides IIIF image URLs in the format:
        https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg

        The 843px width is AIC's official recommendation because it's the most
        common size used by their website, maximizing CDN cache hit rates.
        Height is auto-calculated to maintain aspect ratio.
        """
        image_id = raw_json.get("image_id")
        if not image_id:
            return None

        return f"https://www.artic.edu/iiif/2/{image_id}/full/843,/0/default.jpg"

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """
        Extract work types from AIC artwork_type_title and classification_title.

        AIC provides:
        - artwork_type_title: "Painting", "Print", "Sculpture", etc. (most general)
        - classification_title: "oil on canvas", "woodblock print", etc. (more specific)

        We'll try to only use artwork_type_title for simplicity.
        """
        work_types = set()

        artwork_type = raw_json.get("artwork_type_title", "").lower()
        classification = raw_json.get("classification_title", "").lower()

        assert artwork_type in (
            "painting",
            "drawing and watercolor",
            "print",
            "miniature painting",
            "design",
        )

        if artwork_type == "drawing and watercolor":
            if classification in ["watercolor", "pastel", "gouache", "aquatint"]:
                work_types.add(classification)  # Use more specific type if available
            else:
                work_types.add("drawing")  # Default to drawing if unsure
        elif artwork_type == "miniature painting":
            work_types.update({"miniature", "painting"})
        elif artwork_type in ("painting", "print", "design"):
            work_types.add(artwork_type)
        else:
            raise Exception("Unexpected work type")

        # Above should ensure that all artworks have a searchable work type.
        # For extra info, we also add the classification:
        # (Optional - I could remove this)
        work_types.add(classification)

        print(f"Work types: {work_types}")
        return list(work_types)

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract title from AIC title field."""
        return raw_json.get("title")

    def extract_artists(self, raw_json: dict) -> list[str]:
        """
        Extract artist names from AIC artist_title field.

        AIC provides:
        - artist_title: "Vincent van Gogh" (clean artist name)
        - artist_display: "Vincent van Gogh (Dutch, 1853–1890)" (includes dates/nationality)

        We use artist_title for cleaner data.
        """
        artist = []

        artist_title = raw_json.get("artist_title")
        if artist_title:
            artist.append(artist_title)

        return artist

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Extract production dates from AIC date_start and date_end.

        AIC provides dates as integers (not strings!), which is very clean.
        No parsing needed.
        """
        date_start = raw_json.get("date_start")
        date_end = raw_json.get("date_end")

        # AIC provides integers directly, but we'll safely convert just in case
        production_date_start = None
        production_date_end = None

        if date_start is not None:
            try:
                production_date_start = int(date_start)
            except (ValueError, TypeError):
                pass

        if date_end is not None:
            try:
                production_date_end = int(date_end)
            except (ValueError, TypeError):
                pass

        return production_date_start, production_date_end

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """
        Extract period from AIC date_display field.

        This is the human-readable date string prepared for display,
        e.g., "1889", "1887", "c. 1650", etc.
        """
        return raw_json.get("date_display")

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """
        Extract full resolution image URL from AIC image_id using IIIF API.

        We use a larger size for the full image URL.
        """
        image_id = raw_json.get("image_id")
        if not image_id:
            return None

        # Request full size (using 'full' for both dimensions)
        return f"https://www.artic.edu/iiif/2/{image_id}/full/full/0/default.jpg"
