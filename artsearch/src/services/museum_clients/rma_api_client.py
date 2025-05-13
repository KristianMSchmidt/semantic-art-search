from collections import defaultdict
import re
from typing import Any
from urllib.parse import parse_qs, urlparse
import xmltodict
import requests
from artsearch.src.services.museum_clients.base_client import (
    MuseumAPIClient,
    ArtworkPayload,
    ParsedAPIResponse,
)


class RMAAPIClient(MuseumAPIClient):
    BASE_URL = "https://data.rijksmuseum.nl/oai?verb=GetRecord&metadataPrefix=edm&identifier=https://id.rijksmuseum.nl/"
    BASE_SEARCH_URL = "https://data.rijksmuseum.nl/search/collection"

    def get_thumbnail_url(self, inventory_number: str) -> str:
        url = f"{RMAAPIClient.BASE_SEARCH_URL}?objectNumber={inventory_number}"
        response = self.http_session.get(url)
        response.raise_for_status()
        data = response.json()
        items = data["orderedItems"]
        assert len(items) == 1, (
            f"Expected 1 item for inventory number {inventory_number}, but got {len(items)}"
        )
        item_id = items[0]["id"].split("/")[-1]
        rdf_data = get_record_rdf_data(item_id, self.http_session)
        assert rdf_data is not None, f"Failed to fetch RDF data for {item_id}"
        image_url = extract_image_url(rdf_data)
        assert image_url is not None, (
            f"Failed to extract image URL for {inventory_number}"
        )
        # If image_url ends with ".jpg:", then strip the colon
        if image_url.endswith(".jpg:"):
            image_url = image_url[:-1]
        return image_url

    def _process_item(self, item: dict[str, Any]) -> ArtworkPayload | None:
        """
        item: {'id': 'https://id.rijksmuseum.nl/2006375', 'type': 'HumanMadeObject'}
        """
        item_id = item["id"].split("/")[-1]
        return extract_artwork_payload(item_id, self.http_session)

    def _extract_items(self, raw_data: dict[str, Any]) -> ParsedAPIResponse:
        total_count = raw_data["partOf"]["totalItems"]
        items_list = raw_data.get("orderedItems", [])
        next = raw_data.get("next", None)
        next_page_token = extract_query_param(next["id"], "pageToken") if next else None
        return ParsedAPIResponse(
            total_count=total_count,
            next_page_token=next_page_token,
            items_list=items_list,
        )


def extract_query_param(url: str, query_param_name: str) -> str | None:
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    query_param = query_params.get(query_param_name)
    if query_param:
        return query_param[0]  # parse_qs returns a list for each key
    return None


"""
Helper functions to fetch data from the Rijksmuseum API, processes it, and uploads it
to a Qdrant collection.

Abbreviations used in the Rijksmuseum:
- OAI-PMH: Open Archives Initiative Protocol for Metadata Harvesting
- cho: cultural heritage object
- ore: Object Reuse and Exchange
- edm: Europeana Data Model
- rdf: Resource Description Framework
- dc: Dublin Core. Refers to the original 15 core metadata elements defined by the Dublin Core standard.
       Dublin Core Metadata Initiative
- dcterms: Dublin Core Terms (an extension of the original Dublin Core).
          Use dcterms when you need more detailed, structured, or semantic precision.
- skos: Simple Knowledge Organization System
"""


STATS = defaultdict(int)
WORKTYPES = defaultdict(int)


def check_rights(rights: str | None) -> bool:
    """
    Check if the rights string indicates public domain status.
    """
    return rights == "https://creativecommons.org/publicdomain/mark/1.0/"


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


def extract_provided_cho(rdf_data: dict[str, Any]) -> dict[str, Any] | None:
    provided_cho = rdf_data.get("ore:Aggregation", {}).get("edm:aggregatedCHO", {}).get(
        "edm:ProvidedCHO"
    ) or rdf_data.get("edm:ProvidedCHO")

    if not provided_cho:
        return None

    return provided_cho


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


def normalize_to_list(item):
    if item is None:
        return []
    if isinstance(item, list):
        return item
    return [item]


def extract_rights(provided_cho: dict[str, Any]) -> str | None:
    rights_data = provided_cho.get("dc:rights")
    if not rights_data:
        STATS["no dc:rights"] += 1
        if "rights" in str(provided_cho):
            STATS["no dc:rights but rights in str"] += 1
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

    print("[WARN] Neither @rdf:resource nor #text found in dc:rights")
    return None


def extract_title(rdf_data: dict[str, Any]) -> str | None:
    provided_cho = extract_provided_cho(rdf_data)
    if not provided_cho:
        STATS["no provided_cho"] += 1
        return None

    title_data = provided_cho.get("dc:title")

    if not title_data:
        STATS["no dc:title"] += 1
        if "title" in str(rdf_data):
            STATS["no dc:title but title in str"] += 1
        return None

    if isinstance(title_data, list):
        return get_english_text(title_data)
    return title_data.get("#text")


def extract_image_url(rdf_data: dict) -> str | None:
    # Check if ".jpg" is in str(rdf_data):
    if ".jpg" not in str(rdf_data):
        STATS["no .jpg"] += 1
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


def parse_label(label) -> str | None:
    if not label:
        return None
    if isinstance(label, list):
        return get_english_text(label)
    if isinstance(label, dict):
        return label.get("#text")
    return label  # If it's already a string


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
        if "creator" in str(rdf_data):
            STATS["no dc:creator but creator in str"] += 1
        STATS["no_dc_creator"] += 1
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


def extract_object_number(provided_cho: dict[str, Any]) -> str | None:
    object_number = provided_cho.get("dc:identifier")
    if not object_number:
        STATS["no dc:identifier"] += 1
        return None
    if not isinstance(object_number, str):
        STATS["object_number is not str"] += 1
        return None
    return object_number


def get_record_rdf_data(
    item_id: str, http_session: requests.Session
) -> dict[str, Any] | None:
    """
    Fetches the record data for a given item ID from the Rijksmuseum API.
    Args:
        item_id: The ID of the item to fetch.
    Returns:
        The record data as a dictionary, or None if not found.
    """
    GET_RECORD_URL = "https://data.rijksmuseum.nl/oai?verb=GetRecord&metadataPrefix=edm&identifier=https://id.rijksmuseum.nl/"
    item_url = GET_RECORD_URL + item_id
    response = http_session.get(item_url)
    if response.status_code != 200:
        print(f"Failed to fetch data for item ID {item_id}: {response.status_code}")
        return None
    # Parse XML to dictionary
    data = xmltodict.parse(response.content)
    rdf_data = data["OAI-PMH"]["GetRecord"]["record"]["metadata"]["rdf:RDF"]
    return rdf_data


def extract_artwork_payload(
    item_id: str, http_session: requests.Session
) -> ArtworkPayload | None:
    # Extract rdf_data
    rdf_data = get_record_rdf_data(item_id, http_session)
    if rdf_data is None:
        STATS["no rdf_data"] += 1
        return None

    # Extract provided_cho
    provided_cho = extract_provided_cho(rdf_data)
    if provided_cho is None:
        STATS["no_provided_cho"] += 1
        return None

    # Extract object number
    object_number = extract_object_number(provided_cho)

    # Extract rights
    rights = extract_rights(provided_cho)
    is_public_domain = check_rights(rights)
    if not is_public_domain:
        STATS["not_public_domain"] += 1

    # Extract creation date
    creation_date_str = extract_creation_date(provided_cho)
    production_years = extract_production_years(creation_date_str)
    if not production_years:
        STATS["no_creation_date"] += 1
    else:
        production_date_start, production_date_end = production_years

    # Extract title
    title = extract_title(rdf_data)
    if title is None:
        STATS["title is None"] += 1
    elif title == "":
        title = "No title"
        STATS["empty_title"] += 1

    # Extract image URL
    image_url = extract_image_url(rdf_data)
    image_url = image_url if is_valid_image_url(image_url) else None
    if not image_url:
        STATS["no_image_url"] += 1

    # Extract artist
    artist_names = extract_artist_names(rdf_data)
    if not artist_names:
        STATS["no_artist_name"] += 1

    # Extract work types
    work_types = extract_worktypes(rdf_data)
    if not work_types:
        # I could set it to ['painting'] in this case or whatever I have searched for
        STATS["no_work_types"] += 1
    else:
        for work_type in work_types:
            WORKTYPES[work_type] += 1
    required_fields = [
        object_number,
        is_public_domain,
        image_url,
        title,
        artist_names,
        work_types,
        production_years,
    ]
    missing_fields = [field for field in required_fields if not field]

    if missing_fields:
        return None

    if not image_url:
        return None

    if not work_types:
        return None

    if not object_number:
        return None

    try:
        artwork_payload = ArtworkPayload(
            object_number=object_number,
            titles=[{"title": title}],
            work_types=work_types,
            artist=artist_names,
            thumbnail_url=image_url,
            production_date_start=production_date_start,
            production_date_end=production_date_end,
            museum="rma",
        )
    except Exception as e:
        print(f"Error creating ArtworkPayload: {e}")
        artwork_payload = None
    return artwork_payload


def test_extraction():
    next = True
    type = "painting"
    http_session = requests.Session()
    search_url = f"{RMAAPIClient.BASE_SEARCH_URL}?type={type}"
    total_items = 0
    artwork_payloads = []
    while next:
        result = requests.get(search_url).json()
        items = result.get("orderedItems", None)
        next = result.get("next", None)
        if next:
            search_url = next.get("id", None)
            print(search_url)
        total_items += len(items)
        for item in items:
            item_id = item["id"].split("/")[-1]
            artwork_payload = extract_artwork_payload(item_id, http_session)
            if artwork_payload:
                artwork_payloads.append(artwork_payload)
        print(STATS)
        # NB: It seems like a can't do better at extracting the payloads. So next question is how to handle no title and no artist names (and multiple niche work types)
        print("Total items processed:", total_items)
        print("Artwork payloads:", len(artwork_payloads))
    print("Done!")
    print("Total items:", total_items)


if __name__ == "__main__":
    test_extraction()
