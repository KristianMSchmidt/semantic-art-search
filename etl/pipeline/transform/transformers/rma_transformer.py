from typing import Optional, Any
import re
from etl.pipeline.transform.base_transformer import BaseTransformer
from etl.pipeline.transform.utils import get_searchable_work_types
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

    def extract_searchable_work_types(self, raw_json: dict) -> list[str]:
        """Extract searchable work types using current helper function."""
        # Default implementation using extracted work type and helper function.
        # We could make a version that is both museum specific and independent of the extracted work types, if needed.
        work_types = self.extract_work_types(raw_json)
        return get_searchable_work_types(work_types)

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

    def extract_creation_date_string(self, raw_json: dict) -> Optional[str]:
        """Extract creation date string from RMA provided CHO."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})
        provided_cho = extract_provided_cho(rdf)

        if provided_cho:
            return extract_creation_date(provided_cho)
        return None

    def extract_production_dates(
        self, raw_json: dict
    ) -> tuple[Optional[int], Optional[int]]:
        """Extract production dates from RMA creation date."""
        creation_date_str = self.extract_creation_date_string(raw_json)
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

    def extract_description(self, raw_json: dict) -> Optional[str]:
        """Extract description from RMA provided CHO."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})
        provided_cho = extract_provided_cho(rdf)

        if provided_cho:
            return extract_description(provided_cho)
        return None

    def extract_medium(self, raw_json: dict) -> Optional[list[str]]:
        """Extract medium from RMA RDF data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        return extract_medium(rdf)

    def extract_creator_info(self, raw_json: dict) -> list[dict[str, Any]]:
        """Extract comprehensive creator information for LLM consumption."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        return extract_creator_info(rdf)

    def extract_references(self, raw_json: dict) -> Optional[list[str]]:
        """Extract bibliographic references from RMA RDF data."""
        metadata = raw_json.get("metadata", {})
        rdf = metadata.get("rdf:RDF", {})

        return extract_references(rdf)


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


def extract_description(provided_cho: dict[str, Any]) -> str | None:
    description_data = provided_cho.get("dc:description")

    if not description_data:
        return None

    if isinstance(description_data, list):
        return get_english_text(description_data)
    return description_data.get("#text")


def extract_references(rdf_data: dict[str, Any]) -> list[str] | None:
    """
    Extract bibliographic references from dcterms:isReferencedBy.
    Only returns direct text citations, excludes resource URLs.

    Example return:
    [
        "E. Hartkamp-Joxis, 'Van Doornik naar Smyrna...', Jong Holland 12 (1996) nr. 1, p. 21-24.",
        "I. de Roode, 'De Koninklijke Vereenigde...', Jaarboek 2006 (2007), p. 70-71."
    ]
    """
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        return None

    reference_data = provided_cho.get("dcterms:isReferencedBy")
    if not reference_data:
        return None

    # Normalize to list
    reference_data = normalize_to_list(reference_data)

    references = []

    for item in reference_data:
        # Case 1: Direct string (bibliographic citation)
        if isinstance(item, str):
            references.append(item)
            continue

        # Case 2: Dictionary - check if it has text content
        if isinstance(item, dict):
            # Skip resource URLs (only have @rdf:resource)
            if "@rdf:resource" in item and "#text" not in item:
                continue

            # Extract text content if present
            text = item.get("#text")
            if text:
                references.append(text)
                continue

            # Try parse_label as fallback for other text formats
            label = parse_label(item)
            if label:
                references.append(label)

    return references if references else None


def extract_medium(rdf_data: dict[str, Any]) -> list[str] | None:
    """
    Extract medium from RMA data.
    Handles dcterms:medium with resource references to skos:Concept.
    Returns list of medium strings (e.g., ["oil paint", "panel"]).
    """
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        return None

    medium_data = provided_cho.get("dcterms:medium")
    if not medium_data:
        return None

    # Normalize to list
    medium_data = normalize_to_list(medium_data)

    # Check if inline skos:Concept exists
    inline_mediums = [item for item in medium_data if "skos:Concept" in item]

    mediums = []

    if inline_mediums:
        # Extract labels directly from inline skos:Concept
        for item in inline_mediums:
            concept = item["skos:Concept"]
            labels = concept.get("skos:prefLabel")
            label = parse_label(labels)
            if label:
                mediums.append(label)
    else:
        # Fall back to global lookup if using @rdf:resource
        concepts = rdf_data.get("skos:Concept")
        if not concepts:
            return None

        # Extract resource IDs
        medium_ids = []
        for item in medium_data:
            if isinstance(item, dict) and "@rdf:resource" in item:
                medium_ids.append(item["@rdf:resource"])

        if not medium_ids:
            return None

        # Build concept lookup
        concept_lookup = {
            concept["@rdf:about"]: concept["skos:prefLabel"]
            for concept in normalize_to_list(concepts)
            if "@rdf:about" in concept and "skos:prefLabel" in concept
        }

        # Look up labels for each medium ID
        for medium_id in medium_ids:
            labels = concept_lookup.get(medium_id)
            if labels:
                label = parse_label(labels)
                if label:
                    mediums.append(label)

    return mediums if mediums else None


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


def extract_creator_info(rdf_data: dict) -> list[dict[str, Any]]:
    """
    Extract comprehensive creator information for LLM consumption.
    Returns list of dictionaries with all available creator fields.

    Example return value:
    [
        {
            "name": "Rembrandt van Rijn",
            "birth_date": "1606",
            "death_date": "1669",
            "place_of_birth": "Leiden",
            "place_of_death": "Amsterdam",
            "biographical_info": "Dutch painter and printmaker..."
        }
    ]
    """
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        return []

    dc_creator = provided_cho.get("dc:creator")
    if not dc_creator:
        return []

    creators = normalize_to_list(dc_creator)
    creator_info_list = []

    for creator in creators:
        # Case 1: Direct string - just name
        if isinstance(creator, str):
            creator_info_list.append({"name": creator})
            continue

        if not isinstance(creator, dict):
            continue

        # Extract agent data from different sources
        agent_data = None

        # Case 2: Embedded edm:Agent
        if "edm:Agent" in creator:
            agent_data = creator["edm:Agent"]

        # Case 3: Embedded rdf:Description
        elif "rdf:Description" in creator:
            agent_data = creator["rdf:Description"]

        # Case 4: Reference via @rdf:resource
        elif "@rdf:resource" in creator:
            ref = creator["@rdf:resource"]
            agent_data = resolve_agent_data(rdf_data, ref)

        if agent_data:
            creator_info = extract_agent_fields(agent_data)
            if creator_info:
                creator_info_list.append(creator_info)

    return creator_info_list


def resolve_agent_data(rdf_data: dict, ref: str) -> dict | None:
    """
    Resolve full agent data from @rdf:resource reference.
    Returns the complete agent/description dictionary.
    """
    # Search edm:Agent first
    agents = normalize_to_list(rdf_data.get("edm:Agent"))
    for agent in agents:
        if agent.get("@rdf:about") == ref:
            return agent

    # If not found, search rdf:Description
    descriptions = normalize_to_list(rdf_data.get("rdf:Description"))
    for desc in descriptions:
        if desc.get("@rdf:about") == ref:
            return desc

    return None


def extract_agent_fields(agent_data: dict) -> dict[str, Any]:
    """
    Extract all available fields from an agent/description element.
    Returns dictionary with all found fields for LLM consumption.
    """
    info = {}

    # Name (most important)
    name = parse_label(agent_data.get("skos:prefLabel"))
    if name:
        info["name"] = name

    # Alternative names
    alt_label = parse_label(agent_data.get("skos:altLabel"))
    if alt_label:
        info["alternative_name"] = alt_label

    # Birth/death dates (various possible field names)
    birth_date = parse_label(agent_data.get("edm:begin")) or parse_label(
        agent_data.get("rdaGr2:dateOfBirth")
    )
    if birth_date:
        info["birth_date"] = birth_date

    death_date = parse_label(agent_data.get("edm:end")) or parse_label(
        agent_data.get("rdaGr2:dateOfDeath")
    )
    if death_date:
        info["death_date"] = death_date

    # Places (can be nested edm:Place elements)
    birth_place = extract_place(agent_data.get("rdaGr2:placeOfBirth"))
    if birth_place:
        info["place_of_birth"] = birth_place

    death_place = extract_place(agent_data.get("rdaGr2:placeOfDeath"))
    if death_place:
        info["place_of_death"] = death_place

    # Biographical information
    bio_info = parse_label(agent_data.get("rdaGr2:biographicalInformation"))
    if bio_info:
        info["biographical_info"] = bio_info

    # Profession/occupation (can be multiple nested skos:Concept elements)
    # Commenting professions out, as they seem to very often be boilerplate (painter, print maker, draughtsman) leading to boring and
    # repetitive descriptions.
    # professions = extract_professions(agent_data.get("rdaGr2:professionOrOccupation"))
    # if professions:
    #    info["occupations"] = professions

    # Nationality
    nationality = parse_label(agent_data.get("rdaGr2:countryAssociatedWithThePerson"))
    if nationality:
        info["nationality"] = nationality

    # Gender
    gender = parse_label(agent_data.get("rdaGr2:gender"))
    if gender:
        info["gender"] = gender

    # Any other interesting fields we find
    # dc:identifier - identifier
    identifier = parse_label(agent_data.get("dc:identifier"))
    if identifier:
        info["identifier"] = identifier

    return info


def extract_place(place_data: dict | list | str | None) -> str | None:
    """
    Extract place name from nested edm:Place structure or direct string.

    Example input:
    {
        "edm:Place": {
            "@rdf:about": "https://id.rijksmuseum.nl/230168",
            "skos:prefLabel": [
                {"@xml:lang": "en", "#text": "Amsterdam"},
                {"@xml:lang": "nl", "#text": "Amsterdam"}
            ]
        }
    }
    """
    if not place_data:
        return None

    # Direct string
    if isinstance(place_data, str):
        return place_data

    # Nested edm:Place
    if isinstance(place_data, dict):
        edm_place = place_data.get("edm:Place")
        if edm_place:
            return parse_label(edm_place.get("skos:prefLabel"))
        # Fallback: try to parse as label directly
        return parse_label(place_data)

    return None


def extract_professions(profession_data: dict | list | str | None) -> list[str] | None:
    """
    Extract professions from nested skos:Concept structure(s).
    Can handle single or multiple professions.

    Example input (single):
    {
        "skos:Concept": {
            "@rdf:about": "https://id.rijksmuseum.nl/2202217",
            "skos:prefLabel": [
                {"@xml:lang": "en", "#text": "painter"},
                {"@xml:lang": "nl", "#text": "schilder"}
            ]
        }
    }

    Example input (multiple):
    [
        {"skos:Concept": {...}},
        {"skos:Concept": {...}}
    ]
    """
    if not profession_data:
        return None

    professions = []

    # Normalize to list
    profession_list = normalize_to_list(profession_data)

    for item in profession_list:
        # Direct string
        if isinstance(item, str):
            professions.append(item)
            continue

        # Nested skos:Concept
        if isinstance(item, dict):
            concept = item.get("skos:Concept")
            if concept:
                label = parse_label(concept.get("skos:prefLabel"))
                if label:
                    professions.append(label)
            else:
                # Fallback: try to parse as label directly
                label = parse_label(item)
                if label:
                    professions.append(label)

    return professions if professions else None


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
