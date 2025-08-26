from typing import Optional, Any
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
)
from etl.pipeline.transform.models import TransformedArtworkData


def transform_smk_data(
    raw_json: dict, museum_object_id: str
) -> Optional[TransformedArtworkData]:
    """
    Transform SMK raw JSON data to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Required field: object_number
        object_number = raw_json.get("object_number")
        if not object_number:
            return None

        # Required field: thumbnail_url
        thumbnail_url = raw_json.get("image_thumbnail")
        if not thumbnail_url:
            return None

        # Extract work types
        work_types = []
        object_names = raw_json.get("object_names", [])
        if object_names:
            work_types = [
                obj_name.get("name", "").lower()
                for obj_name in object_names
                if obj_name.get("name")
            ]

        # Required field: searchable_work_types
        searchable_work_types = get_searchable_work_types(work_types)
        if not searchable_work_types:
            return None

        # Extract title
        titles = raw_json.get("titles", [])
        title = extract_primary_title(titles)

        # Extract artists
        artists_raw = raw_json.get("artist", [])
        artist = extract_artist_names(artists_raw)

        # Extract production dates
        production_dates = raw_json.get("production_date", [])
        production_date_start = None
        production_date_end = None
        period = None

        if production_dates and len(production_dates) > 0:
            date_obj = production_dates[0]
            if isinstance(date_obj, dict):
                # Extract period from production_date if it exists
                period = date_obj.get("period")

                start_date = date_obj.get("start")
                end_date = date_obj.get("end")

                if start_date:
                    production_date_start = safe_int_from_date(start_date)
                if end_date:
                    production_date_end = safe_int_from_date(end_date)

        # Extract image URLs - store IIIF ID for flexible usage
        image_url = raw_json.get("image_iiif_id")

        # Return transformed data as Pydantic model
        return TransformedArtworkData(
            object_number=object_number,
            title=title,
            work_types=work_types,
            searchable_work_types=searchable_work_types,
            artist=artist,
            production_date_start=production_date_start,
            production_date_end=production_date_end,
            period=period,
            thumbnail_url=str(thumbnail_url),
            museum_slug="smk",
            museum_db_id=None,
            image_url=image_url,
            # Processing flags default to False
            image_loaded=False,
            text_vector_clip=False,
            image_vector_clip=False,
            text_vector_jina=False,
            image_vector_jina=False,
        )

    except Exception as e:
        print(f"SMK transform error for {museum_object_id}: {e}")
        return None


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
