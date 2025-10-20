from typing import Optional, Any
import re
from etl.pipeline.transform.base_transformer import BaseTransformer
from etl.pipeline.shared.rma_utils import extract_provided_cho, extract_object_number


class RmaTransformer(BaseTransformer):
    """RMA (Rijksmuseum Amsterdam) data transformer."""

    museum_slug = "rma"

    def should_skip_record(self, raw_json: dict) -> tuple[bool, str]:
        """Check if RMA record should be skipped based on public domain status."""
        metadata = raw_json.get("metadata", {})
        if not metadata:
            return True, "Missing metadata"

        rdf = metadata.get("rdf:RDF", {})
        if not rdf:
            return True, "Missing rdf"

        provided_cho = extract_provided_cho(rdf)
        if not provided_cho:
            return True, "Missing provided_cho"

        # Check public domain status
        rights = extract_rights(provided_cho)
        is_public_domain = check_rights(rights)
        if not is_public_domain:
            return True, "Not public domain"

        # Validate object number from RDF data
        rdf_object_number = extract_object_number(provided_cho)
        if not rdf_object_number:
            return True, "Missing RDF object number"

        return False, ""

    def extract_thumbnail_url(self, raw_json: dict) -> Optional[str]:
        """Extract thumbnail URL from RMA image data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        image_url = extract_image_url_from_rdf(rdf)
        if not image_url or not is_valid_image_url(image_url):
            return None

        # Adjust thumbnail size for faster loading
        return resize_image_to_thumbnail(image_url)

    def extract_work_types(self, raw_json: dict) -> list[str]:
        """Extract work types from RMA RDF data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        work_types = extract_worktypes(rdf)
        return work_types or []

    def extract_title(self, raw_json: dict) -> Optional[str]:
        """Extract title from RMA provided CHO."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})
        provided_cho = extract_provided_cho(rdf)

        if provided_cho:
            return extract_title(provided_cho)
        return None

    def extract_artists(self, raw_json: dict) -> list[str]:
        """Extract artist names from RMA RDF data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        return extract_artist_names(rdf)

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """Extract production dates from RMA creation date."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})
        provided_cho = extract_provided_cho(rdf)

        if provided_cho:
            creation_date_str = extract_creation_date(provided_cho)
            production_years = extract_production_years(creation_date_str)
            if production_years:
                return production_years

        return None, None

    def extract_period(self, raw_json: dict) -> Optional[str]:
        """Extract period from RMA data - not currently used."""
        return None

    def extract_image_url(self, raw_json: dict) -> Optional[str]:
        """Extract original resolution image URL from RMA data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        image_url = extract_image_url_from_rdf(rdf)
        if image_url and is_valid_image_url(image_url):
            return image_url
        return None


#### RMA helpers and utility functions #####


def resize_image_to_thumbnail(image_url: str, width=800) -> str:
    """
    Adjusts IIIF image URLs to thumbnail size.
    """
    if image_url.startswith("https://iiif.micr.io/") and "/full/max/" in image_url:
        return image_url.replace("/full/max/", f"/full/{width},/")

    return image_url


def extract_image_url_from_rdf(rdf_data: dict) -> str | None:
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
