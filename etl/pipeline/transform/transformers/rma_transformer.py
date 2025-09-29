from typing import Optional, Any
import re
from etl.pipeline.transform.utils import (
    get_searchable_work_types,
)
from etl.pipeline.transform.models import TransformedArtworkData
from etl.pipeline.transform.models import TransformerArgs
from etl.pipeline.shared.rma_utils import extract_provided_cho, extract_object_number


def transform_rma_data(
    transformer_args: TransformerArgs,
) -> Optional[TransformedArtworkData]:
    """
    Transform raw RMA metadata object to TransformedArtworkData.

    Returns TransformedArtworkData instance or None if transformation fails.
    """
    try:
        # Museum slug check
        museum_slug = transformer_args.museum_slug
        assert museum_slug == "rma", "Transformer called for wrong museum"

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

        metadata = raw_json.get("metadata", {})
        if not metadata:
            # print("Missing metadata")
            return None

        rdf = metadata.get("rdf:RDF", {})
        if not rdf:
            # print("Missing rdf")
            return None

        provided_cho = extract_provided_cho(rdf)
        if not provided_cho:
            # print("Missing provided_cho")
            return None

        # Extract rights
        rights = extract_rights(provided_cho)
        is_public_domain = check_rights(rights)
        if not is_public_domain:
            # print("Not public domain")
            return None

        # Extract and validate object_number from RDF data
        rdf_object_number = extract_object_number(provided_cho)
        if not rdf_object_number:
            return None

        # Required field: Thumbnail url (from Image url):
        image_url = extract_image_url(rdf)
        if not image_url or not is_valid_image_url(image_url):
            # print("Missing or invalid image URL")
            return None

        # Adjust thumbnail size for faster loading
        thumbnail_url = adjust_thumbnail_size(image_url)

        # Required field: Extract work types
        work_types = extract_worktypes(rdf)
        if not work_types:
            # print("Missing work types")
            return None

        # Required field: searchable_work_types
        searchable_work_types = get_searchable_work_types(work_types)
        if not searchable_work_types:
            return None

        # Extract title
        title = extract_title(provided_cho)

        # Extract artists
        artist = extract_artist_names(rdf)

        # Extract production dates
        creation_date_str = extract_creation_date(provided_cho)
        production_years = extract_production_years(creation_date_str)
        if not production_years:
            # print("Missing production years")
            return None
        else:
            production_date_start, production_date_end = production_years

        period = None  # Don't think I need this for RMA. Haven't looked closely.

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
            thumbnail_url=thumbnail_url,
            museum_slug=museum_slug,
            image_url=image_url,
        )

    except Exception as e:
        print(f"RMA transform error for {object_number}:{museum_db_id}: {e}")
        return None


#### RMA helpers and utility functions #####


def adjust_thumbnail_size(image_url: str, width=600) -> str:
    """
    Adjusts IIIF image thumbnail URLs to use a smaller width instead of 'max' for faster loading.
    """
    if image_url.startswith("https://iiif.micr.io/") and "/full/max/" in image_url:
        return image_url.replace("/full/max/", f"/full/{width},/")

    return image_url


def extract_image_url(rdf_data: dict) -> str | None:
    # Check if ".jpg" is in str(rdf_data):
    if ".jpg" not in str(rdf_data):
        return None

    aggregation = rdf_data.get("ore:Aggregation")
    if not aggregation:
        return None

    # Try edm:isShownBy first
    is_shown_by = aggregation.get("edm:isShownBy")
    if is_shown_by:
        if isinstance(is_shown_by, dict):
            # Case where edm:isShownBy wraps edm:WebResource
            web_resource = is_shown_by.get("edm:WebResource")
            if web_resource:
                return web_resource.get("@rdf:about")
            # Case where it's a direct link
            url = is_shown_by.get("@rdf:resource")
            if url:
                return url

    # Fallback to edm:object
    edm_object = aggregation.get("edm:object")
    if edm_object:
        if isinstance(edm_object, dict):
            # Sometimes it's wrapped in edm:WebResource
            return edm_object.get("@rdf:resource") or edm_object.get(
                "edm:WebResource", {}
            ).get("@rdf:about")
        elif isinstance(edm_object, list):
            return next(
                (t.get("@rdf:resource") for t in edm_object if t.get("@rdf:resource")),
                None,
            )
        elif isinstance(edm_object, str):
            return edm_object

    return None


def is_valid_image_url(url: str | None) -> bool:
    if not url:
        return False
    return url.startswith("https://") and url.endswith(".jpg")


def normalize_to_list(item):
    if item is None:
        return []
    if isinstance(item, list):
        return item
    return [item]


def get_english_text(data: list[dict[str, Any]]) -> str | None:
    """
    Helper function to extract text from a list of dictionaries.
    Prefer English text if available, otherwise Dutch.
    """
    english_text = next(
        (t.get("#text") for t in data if t.get("@xml:lang") == "en"), None
    )
    if english_text:
        return english_text
    dutch_text = next(
        (t.get("#text") for t in data if t.get("@xml:lang") == "nl"), None
    )
    if dutch_text:
        return dutch_text
    return data[0].get("#text")


def parse_label(label) -> str | None:
    if not label:
        return None
    if isinstance(label, list):
        return get_english_text(label)
    if isinstance(label, dict):
        return label.get("#text")
    return label  # If it's already a string


def extract_type_ids(type_resources) -> list[str]:
    """
    Normalize dc:type resources to a list of rdf:about or rdf:resource IDs.

    Handles cases where type_resources is:
    - A dict with '@rdf:resource'
    - A dict with 'skos:Concept'
    - A list of the above
    """
    type_ids = []

    if isinstance(type_resources, dict):
        if "@rdf:resource" in type_resources:
            type_ids.append(type_resources["@rdf:resource"])
        elif "skos:Concept" in type_resources:
            type_ids.append(type_resources["skos:Concept"].get("@rdf:about"))
        else:
            print("[WARN] Unknown dict format in type_resources:", type_resources)

    elif isinstance(type_resources, list):
        for item in type_resources:
            if "@rdf:resource" in item:
                type_ids.append(item["@rdf:resource"])
            elif "skos:Concept" in item:
                type_ids.append(item["skos:Concept"].get("@rdf:about"))
            else:
                print("[WARN] Unknown list item format in type_resources:", item)

    else:
        print("[WARN] Unexpected type_resources format:", type_resources)

    # Filter out any None values just in case
    return [tid for tid in type_ids if tid]


def extract_worktypes(rdf_data: dict[str, Any]) -> list[str] | None:
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        return None

    type_data = provided_cho.get("dc:type")
    if not type_data:
        return None

    # Normalize type_resources to a list
    type_data = normalize_to_list(type_data)

    # Check if inline skos:Concept exists in type_resources
    inline_types = [item for item in type_data if "skos:Concept" in item]

    work_types = []

    if inline_types:
        # Extract labels directly from inline skos:Concept
        for item in inline_types:
            concept = item["skos:Concept"]
            labels = concept.get("skos:prefLabel")
            label = parse_label(labels)
            work_types.append(label)
    else:
        # Fall back to global lookup if using @rdf:resource
        concepts = rdf_data.get("skos:Concept")
        if not concepts:
            print("[WARN] No skos:Concept found for lookup.")
            return None

        type_ids = extract_type_ids(type_data)
        concept_lookup = {
            concept["@rdf:about"]: concept["skos:prefLabel"]
            for concept in concepts
            if "@rdf:about" in concept and "skos:prefLabel" in concept
        }

        for type_id in type_ids:
            labels = concept_lookup.get(type_id)
            if not labels:
                print(f"[WARN] No labels found for type_id: {type_id}")
                continue
            label = parse_label(labels)
            work_types.append(label)

    return work_types if work_types else None


def extract_title(provided_cho: dict[str, Any]) -> str | None:
    title_data = provided_cho.get("dc:title")

    if not title_data:
        return None

    if isinstance(title_data, list):
        return get_english_text(title_data)
    return title_data.get("#text")


def extract_artist_names(rdf_data: dict) -> list[str]:
    """
    Extract one or more artist names from dc:creator.
    Handles edm:Agent, rdf:Description, @rdf:resource references, and direct strings.
    Returns a list of artist names.
    """
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        return []

    dc_creator = provided_cho.get("dc:creator")
    if not dc_creator:
        return []

    creators = normalize_to_list(dc_creator)
    artist_names = []

    for creator in creators:
        assert isinstance(creator, (dict, str)), (
            f"Unexpected type for dc:creator: {type(creator)}"
        )
        # Case 1: Embedded edm:Agent
        if isinstance(creator, dict) and "edm:Agent" in creator:
            label = creator["edm:Agent"].get("skos:prefLabel")
            name = parse_label(label)
            if name:
                artist_names.append(name)
            continue

        # Case 2: Embedded rdf:Description
        if isinstance(creator, dict) and "rdf:Description" in creator:
            label = creator["rdf:Description"].get("skos:prefLabel")
            name = parse_label(label)
            if name:
                artist_names.append(name)
            continue

        # Case 3: Reference via @rdf:resource
        if isinstance(creator, dict) and "@rdf:resource" in creator:
            ref = creator["@rdf:resource"]
            name = resolve_agent_label(rdf_data, ref)
            if name:
                artist_names.append(name)
            continue

        # Case 4: Direct string
        if isinstance(creator, str):
            artist_names.append(creator)
            continue

        print(f"[WARN] Unknown dc:creator format: {creator}")

    return artist_names


def extract_creation_date(provided_cho: dict[str, Any]) -> str | None:
    try:
        date_data = provided_cho["dcterms:created"]
    except KeyError:
        print("KeyError: dcterms:created not found in provided_cho")
        return None
    if date_data:
        if isinstance(date_data, list):
            return get_english_text(date_data)
        return date_data.get("#text")
    return None


def extract_production_years(create_date_str: str | None) -> tuple[int, int] | None:
    if not create_date_str:
        return None

    # Match years with 3 or 4 digits
    years = re.findall(r"\d{3,4}", create_date_str)

    if not years:
        return None

    years = list(map(int, years))

    if len(years) == 1:
        return (years[0], years[0])
    else:
        return (min(years), max(years))


def resolve_agent_label(rdf_data: dict, ref: str) -> str | None:
    """
    Resolve an agent label from @rdf:resource by searching edm:Agent and rdf:Description.
    """
    # Search edm:Agent first
    agents = normalize_to_list(rdf_data.get("edm:Agent"))
    for agent in agents:
        if agent.get("@rdf:about") == ref:
            return parse_label(agent.get("skos:prefLabel"))

    # If not found, search rdf:Description
    descriptions = normalize_to_list(rdf_data.get("rdf:Description"))
    for desc in descriptions:
        if desc.get("@rdf:about") == ref:
            return parse_label(desc.get("skos:prefLabel"))

    print(f"[WARN] Could not resolve agent for reference: {ref}")
    return None


def check_rights(rights: str | None) -> bool:
    """
    Check if the rights string indicates public domain status.
    """
    PD_URLS_GLOBAL = {
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "http://creativecommons.org/publicdomain/zero/1.0/",
        "https://creativecommons.org/publicdomain/mark/1.0/",
        "http://creativecommons.org/publicdomain/mark/1.0/",
    }
    return rights in PD_URLS_GLOBAL


def extract_rights(provided_cho: dict[str, Any]) -> str | None:
    rights_data = provided_cho.get("dc:rights")
    if not rights_data:
        return None

    rights_list = normalize_to_list(rights_data)

    # Prioritize @rdf:resource
    for item in rights_list:
        if isinstance(item, dict) and "@rdf:resource" in item:
            return item["@rdf:resource"]

    # Fallback: Look for English text
    text = get_english_text(rights_list)
    if text:
        return text

    return None
