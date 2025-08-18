from typing import Optional
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
    extract_primary_title,
    extract_artist_names,
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

        # Generate URLs
        object_url = None
        museum_frontend_url = ""
        if object_number:
            object_url = f"https://api.smk.dk/api/v1/art/?object_number={object_number}"
            # Use frontend_url from raw data if available, otherwise generate fallback
            museum_frontend_url = raw_json.get(
                "frontend_url",
                f"https://open.smk.dk/artwork/image/{object_number.lower()}",
            )

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
        print(f"SMK transform error for {museum_object_id}: {e}")
        return None
