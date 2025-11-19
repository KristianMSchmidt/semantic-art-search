"""RMA (Rijksmuseum Amsterdam) metadata processor.

Note: This module uses RMA extraction logic from the ETL pipeline.
This is a known coupling point documented in CLAUDE.md. The extraction
logic is complex (XML/RDF parsing) and shared for pragmatic reasons.
"""

import logging
from typing import Any
from etl.pipeline.transform.transformers.rma_transformer import RmaTransformer

logger = logging.getLogger(__name__)


def clean_rma_metadata(raw_xml_dict: dict) -> dict[str, Any]:
    """Clean and extract RMA metadata for description generation.

    Args:
        raw_xml_dict: Parsed XML from RMA API (converted to dict via xmltodict)

    Returns:
        Cleaned metadata dictionary with extracted fields
    """
    # Extract the record from OAI-PMH structure
    record = raw_xml_dict.get("OAI-PMH", {}).get("GetRecord", {}).get("record", {})

    # Use RMA transformer to extract structured fields
    transformer = RmaTransformer()

    metadata = {
        "artists": transformer.extract_artists(record),
        "title": transformer.extract_title(record),
        "creation_date": transformer.extract_creation_date_string(record),
        "work_types": transformer.extract_work_types(record),
        "medium": transformer.extract_medium(record),
        "description": transformer.extract_description(record),
        "creator_info": transformer.extract_creator_info(record),
        "references": transformer.extract_references(record),
    }

    # Remove None values
    metadata = {k: v for k, v in metadata.items() if v is not None}

    logger.debug(f"Cleaned RMA metadata: {list(metadata.keys())}")
    return metadata
