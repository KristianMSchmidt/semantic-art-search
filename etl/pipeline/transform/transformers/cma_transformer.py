from typing import Optional
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
)
from etl.pipeline.transform.models import TransformedArtworkData


def transform_cma_data(
    raw_json: dict, museum_object_id: str
) -> Optional[TransformedArtworkData]:
    """
    Transform CMA raw JSON data to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Required field: object_number (accession_number)
        object_number = raw_json.get("accession_number")
        if not object_number:
            return None

        # Required field: thumbnail_url
        thumbnail_url = None
        try:
            thumbnail_url = raw_json["images"]["web"]["url"]
        except (KeyError, TypeError):
            return None

        if not thumbnail_url:
            return None

        # Extract work types
        work_types = []
        work_type = raw_json.get("type")
        if work_type:
            work_types = [work_type.lower()]

        # Required field: searchable_work_types
        searchable_work_types = get_searchable_work_types(work_types)
        if not searchable_work_types:
            return None

        # Extract title
        title = raw_json.get("title")

        # Extract artists - CMA has empty creators array, but may have culture
        artist = []
        creators = raw_json.get("creators", [])
        if creators:
            artist = [
                creator.get("description", "").split("(")[0].strip()
                for creator in creators
                if creator.get("description")
            ]

        # If no creators, try culture field
        if not artist:
            culture = raw_json.get("culture", [])
            if culture:
                artist = culture

        # Extract production dates
        production_date_start = None
        production_date_end = None

        start_date = raw_json.get("creation_date_earliest")
        end_date = raw_json.get("creation_date_latest")

        if start_date:
            production_date_start = safe_int_from_date(start_date)
        if end_date:
            production_date_end = safe_int_from_date(end_date)

        # Extract period from creation_date
        period = raw_json.get("creation_date")

        # Extract image URL - use print resolution
        image_url = None
        try:
            image_url = raw_json["images"]["print"]["url"]
        except (KeyError, TypeError):
            pass

        # Use 'url' as frontend_url
        museum_frontend_url = raw_json.get("url", "")
        if not museum_frontend_url:
            museum_frontend_url = f"https://clevelandart.org/art/{object_number}"

        # Generate API object URL
        object_url = None
        if object_number:
            object_url = f"https://openaccess-api.clevelandart.org/api/artworks/?accession_number={object_number}"

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
            museum_slug="cma",
            museum_db_id=str(raw_json.get("id")) if raw_json.get("id") else None,
            museum_frontend_url=museum_frontend_url,
            image_url=image_url,
            object_url=object_url,
            # Processing flags default to False
            image_loaded=False,
            text_vector_clip=False,
            image_vector_clip=False,
            text_vector_jina=False,
            image_vector_jina=False,
        )

    except Exception as e:
        print(f"CMA transform error for {museum_object_id}: {e}")
        return None
