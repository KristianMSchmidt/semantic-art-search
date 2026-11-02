from typing import Optional
from etl.pipeline.transform.base_transformer import BaseTransformer
from etl.pipeline.transform.utils import get_searchable_work_types

IMAGE_BASE_URL = "https://kokoelma.kansallisgalleria.fi"

# Image sizes (longest side, px) the museum serves per image. The thumbnail is
# downscaled to 800px by the image loader.
THUMBNAIL_SIZE = "1000"
FULL_IMAGE_SIZE = "4000"

# English classification names -> our work types. Classifications not listed here
# (e.g. "icon", "Persian miniature") are kept as they are; "Persian miniature"
# still matches the searchable "miniature" work type.
CLASSIFICATION_TO_WORK_TYPE = {
    "graphic arts": "print",
}

# Materials (English) that add a more specific work type, e.g. gouache on ivory miniatures
MATERIAL_WORK_TYPES = {
    "gouache": "gouache",
    "gouache on ivory": "gouache",
    "pastel": "pastel",
    "watercolour": "watercolor",
    "watercolor": "watercolor",
}

# How an attribution is shown before the artist's name, e.g. "Circle of Rembrandt"
ATTRIBUTION_PREFIXES = {
    "attributed to": "Attributed to",
    "follower": "Follower of",
    "workshop": "Workshop of",
    "studio": "Studio of",
    "circle": "Circle of",
    "school": "School of",
    "copy after": "Copy after",
}

# The museum's name for an unknown artist ("artist unknown")
UNKNOWN_ARTIST_NAMES = {"tekijä ei tiedossa"}

MAX_TITLE_LENGTH = 500  # TransformedData.title max_length


def get_localized(value, *languages: str) -> Optional[str]:
    """First non-empty text from a {"en": ..., "fi": ..., "sv": ...} dict."""
    if not isinstance(value, dict):
        return None
    for language in languages or ("en", "fi", "sv"):
        text = (value.get(language) or "").strip()
        if text:
            return text
    return None


def to_year(value) -> Optional[int]:
    """A year from an int or a numeric string (the dump uses ints), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


class FngTransformer(BaseTransformer):
    """Finnish National Gallery (Kansallisgalleria) data transformer."""

    museum_slug = "fng"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """Skip records without a CC0 image (should already be filtered in extraction)."""
        if (raw_json.get("image") or {}).get("license") != "CC0":
            return True, "Image not CC0"
        return False, ""

    def _image_url(self, raw_json: dict, size: str) -> Optional[str]:
        path = ((raw_json.get("image") or {}).get("jpg") or {}).get(size)
        return f"{IMAGE_BASE_URL}{path}" if path else None

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        return self._image_url(raw_json, THUMBNAIL_SIZE)

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        return self._image_url(raw_json, FULL_IMAGE_SIZE)

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """
        Work types from the English classifications, plus a few materials.

        E.g. classifications ["painting", "miniature"] and material "gouache on ivory"
        -> ["painting", "miniature", "gouache"].
        """
        work_types: list[str] = []
        for classification in raw_json.get("classifications") or []:
            name = (classification.get("en") or "").strip()
            if name:
                work_types.append(CLASSIFICATION_TO_WORK_TYPE.get(name, name.lower()))
        for material in raw_json.get("materials") or []:
            work_type = MATERIAL_WORK_TYPES.get((material.get("en") or "").strip().lower())
            if work_type:
                work_types.append(work_type)
        return list(dict.fromkeys(work_types))  # Dedupe, keep order

    def extract_searchable_work_types(self, raw_json: dict) -> list[str]:
        return get_searchable_work_types(self.extract_work_types(raw_json))

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """English title if there is one, else Finnish, else Swedish."""
        title = get_localized(raw_json.get("title"))
        return title[:MAX_TITLE_LENGTH] if title else None

    def extract_artists(self, raw_json: dict) -> list[str]:
        """
        Artist names, with attributions such as "Workshop of" in front.

        Only people with the Artist role (or no role) count; casters and
        manufacturers of sculptures are left out. Unknown artists give no name.
        """
        artists = []
        for person in self._artist_people(raw_json):
            name = " ".join(
                part.strip()
                for part in (person.get("firstName"), person.get("familyName"))
                if part and part.strip()
            )
            if not name or name.lower() in UNKNOWN_ARTIST_NAMES:
                continue
            attribution = get_localized(person.get("attribution"), "en")
            prefix = ATTRIBUTION_PREFIXES.get((attribution or "").lower())
            artists.append(f"{prefix} {name}" if prefix else name)
        return artists

    def _artist_people(self, raw_json: dict) -> list[dict]:
        """People with the Artist role (or no role), not casters, manufacturers etc."""
        people = []
        for person in raw_json.get("people") or []:
            role = get_localized(person.get("role"), "en")
            if not role or role.lower() == "artist":
                people.append(person)
        return people

    def _artist_lifespan(self, raw_json: dict) -> Optional[tuple[int, int]]:
        people = self._artist_people(raw_json)
        if len(people) != 1:
            return None
        birth, death = people[0].get("birthYear"), people[0].get("deathYear")
        return (birth, death) if birth and death else None

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """
        Production years from yearFrom/yearTo (yearTo is empty for single years).

        Dates equal to the artist's lifespan are a placeholder for "undated", as at
        NGA, so they are treated as unknown.
        """
        start = to_year(raw_json.get("yearFrom"))
        end = to_year(raw_json.get("yearTo"))
        if start is None:
            start = end  # Only an end year
        if start is None:
            return None, None
        if end is None or end < start:
            end = start
        if (start, end) == self._artist_lifespan(raw_json):
            return None, None
        return start, end

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Readable date, e.g. "1888", "1850–1855" or "circa 1880"."""
        start, end = self.extract_production_dates(raw_json)
        if start is None:
            return None
        period = str(start) if end == start else f"{start}–{end}"
        prefix = get_localized(raw_json.get("datePrefix"), "en")
        return f"{prefix} {period}" if prefix else period
