"""Common utilities for metadata processing."""


def remove_fields(metadata: dict, fields_to_remove: list[str]) -> dict:
    """Remove specified fields from metadata dictionary.

    Args:
        metadata: Source metadata dictionary
        fields_to_remove: List of field names to remove

    Returns:
        New dictionary with specified fields removed
    """
    result = metadata.copy()
    for field in fields_to_remove:
        result.pop(field, None)
    return result


def remove_empty_fields(metadata: dict) -> dict:
    """Remove fields with empty values (None, empty string, empty list, empty dict).

    Args:
        metadata: Source metadata dictionary

    Returns:
        New dictionary with empty fields removed
    """
    return {k: v for k, v in metadata.items() if v not in (None, "", [], {})}
