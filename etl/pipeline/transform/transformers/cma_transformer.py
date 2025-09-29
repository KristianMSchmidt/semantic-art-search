from typing import Optional
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
)
from etl.pipeline.transform.models import TransformedArtworkData
from etl.pipeline.transform.models import TransformerArgs


def transform_cma_data(
    transformer_args: TransformerArgs,
) -> Optional[TransformedArtworkData]:
    """
    Transform raw CMA metadata object to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Museum slug check
        museum_slug = transformer_args.museum_slug
        assert museum_slug == "cma", "Transformer called for wrong museum"

        # Object number
        object_number = transformer_args.object_number
        if not object_number:
            return None

        # Museum DB ID
        museum_db_id = transformer_args.museum_db_id
        if not museum_db_id:
            return None

        # Raw JSON data
        raw_json = transformer_args.raw_json
        if not raw_json or not isinstance(raw_json, dict):
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

        # Return transformed data as Pydantic model
        return TransformedArtworkData(
            object_number=object_number,
            museum_db_id=museum_db_id,
            title=title,
            work_types=work_types,
            searchable_work_types=searchable_work_types,
            artist=artist,
            production_date_start=production_date_start,
            production_date_end=production_date_end,
            period=period,
            thumbnail_url=str(thumbnail_url),
            museum_slug=museum_slug,
            image_url=image_url,
        )

    except Exception as e:
        print(f"CMA transform error for {object_number}:{museum_db_id}: {e}")
        return None
