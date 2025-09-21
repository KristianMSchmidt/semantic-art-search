"""
Shared utilities for RMA (Rijksmuseum) data processing.

These functions handle the complex nested JSON structure that RMA uses
in both extraction and transformation pipeline stages.
"""

from typing import Any


def extract_provided_cho(rdf_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract the ProvidedCHO section from RMA's complex nested structure.

    RMA data comes in a nested format with multiple possible paths to the
    ProvidedCHO (Provided Cultural Heritage Object) information.

    Args:
        rdf_data: The RDF section from RMA's metadata

    Returns:
        The ProvidedCHO dictionary if found, None otherwise
    """
    if not rdf_data:
        return None

    provided_cho = rdf_data.get("ore:Aggregation", {}).get("edm:aggregatedCHO", {}).get(
        "edm:ProvidedCHO"
    ) or rdf_data.get("edm:ProvidedCHO")

    return provided_cho


def extract_object_number(provided_cho: dict[str, Any]) -> str | None:
    """
    Extract object number (dc:identifier) from ProvidedCHO.

    The object number serves as the stable public identifier for RMA artworks,
    equivalent to accession numbers in other museums.

    Args:
        provided_cho: The ProvidedCHO dictionary from RMA data

    Returns:
        The object number string if found and valid, None otherwise
    """
    if not provided_cho:
        return None

    object_number = provided_cho.get("dc:identifier")
    if not object_number or not isinstance(object_number, str):
        return None
    return object_number