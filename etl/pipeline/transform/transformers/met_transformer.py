from typing import Optional
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
    safe_int_from_date,
)
from etl.pipeline.transform.models import TransformedArtworkData


# MET classification mapping (from the API client)
MET_CLASSIFICATION_TO_WORK_TYPE = {
    "paintings": "painting",
    "miniatures": "miniature",
    "pastels": "pastel",
    "oil sketches on paper": "oil sketch on paper",
    "drawings": "drawing",
    "prints": "print",
}

API_OBJECTS_BASE_URL = (
    "https://collectionapi.metmuseum.org/public/collection/v1/objects"
)


def transform_met_data(
    raw_json: dict, museum_object_id: str
) -> Optional[TransformedArtworkData]:
    """
    Transform MET raw JSON data to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Skip non-public domain items
        if not raw_json.get("isPublicDomain"):
            return None

        # Required field: object_number (accessionNumber)
        object_number = raw_json.get("accessionNumber")
        if not object_number:
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
                f"MET: No searchable work types found for {museum_object_id}, classification='{classification}', objectName='{object_name}', work_types={work_types}"
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

        # Use objectURL, fallback to constructed URL
        museum_frontend_url = raw_json.get("objectURL", "")
        if not museum_frontend_url:
            museum_frontend_url = (
                f"https://www.metmuseum.org/art/collection/search/{museum_object_id}"
            )

        # Generate API object URL
        object_url = f"{API_OBJECTS_BASE_URL}/{museum_object_id}"

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
            museum_slug="met",
            museum_db_id=str(raw_json.get("objectID"))
            if raw_json.get("objectID")
            else None,
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
        print(f"MET transform error for {museum_object_id}: {e}")
        return None
