from typing import Optional
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
)
from etl.pipeline.transform.models import TransformedArtworkData
from etl.pipeline.transform.models import TransformerArgs


# MET classification mapping (from the API client)
MET_CLASSIFICATION_TO_WORK_TYPE = {
    "paintings": "painting",
    "miniatures": "miniature",
    "pastels": "pastel",
    "oil sketches on paper": "oil sketch on paper",
    "drawings": "drawing",
    "prints": "print",
}


def transform_met_data(
    transformer_args: TransformerArgs,
) -> Optional[TransformedArtworkData]:
    """
    Transform raw MET metadata object to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Museum slug check
        museum_slug = transformer_args.museum_slug
        assert museum_slug == "met", "Transformer called for wrong museum"

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

        # Skip non-public domain items
        if not raw_json.get("isPublicDomain"):
            return None

        # Required field: thumbnail_url
        thumbnail_url = raw_json.get("primaryImageSmall")
        if not thumbnail_url:
            return None

        # Extract work types from classification and objectName
        work_types = []
        classification = raw_json.get("classification", "").lower().strip()
        object_name = raw_json.get("objectName", "").lower().strip()

        if classification:
            # Handle multiple classifications separated by &
            classification_parts = [part.strip() for part in classification.split("&")]
            for part in classification_parts:
                if part in MET_CLASSIFICATION_TO_WORK_TYPE:
                    work_types.append(MET_CLASSIFICATION_TO_WORK_TYPE[part])
        elif object_name:
            # Use object name directly if no classification
            work_types = [object_name]

        # Required field: searchable_work_types
        searchable_work_types = get_searchable_work_types(work_types)
        if not searchable_work_types:
            print(
                f"MET: No searchable work types found for {object_number}:{museum_db_id}, classification='{classification}', objectName='{object_name}', work_types={work_types}"
            )
            return None

        # Extract title
        title = raw_json.get("title")

        # Extract artists - prefer constituents, fallback to artistDisplayName
        artist = []
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

        # Extract production dates
        production_date_start = None
        production_date_end = None

        begin_date = raw_json.get("objectBeginDate")
        end_date = raw_json.get("objectEndDate")

        if begin_date:
            production_date_start = safe_int_from_date(str(begin_date))
        if end_date:
            production_date_end = safe_int_from_date(str(end_date))

        # Extract period - prefer 'period' field, fallback to 'objectDate'
        period = raw_json.get("period")
        if not period:
            period = raw_json.get("objectDate")

        # Extract image URL - use primaryImage
        image_url = raw_json.get("primaryImage")

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
        print(f"MET transform error for {object_number}:{museum_db_id}: {e}")
        return None
