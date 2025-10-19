import re
from artsearch.src.constants.work_types import SEARCHABLE_WORK_TYPES
from artsearch.src.utils.work_type_utils import get_standardized_work_type


def get_searchable_work_types(work_types: list[str]) -> list[str]:
    """
    Given a list of original work types (not necessarily in English) for a given artwork,
    return a list of standardized searchable work types in English.

    We go to some lengths to map various possible input work types
    (including translations and subtypes) to our standardized set of searchable work types.

    Returns empty list if no searchable work types found (to handle gracefully).
    """
    searchable_work_types = set()
    for work_type in work_types:
        work_type = work_type.lower().strip()

        # Get translated/normalized work type name, if available
        work_type = get_standardized_work_type(work_type)

        # Match searchable work types using word boundaries to avoid false positives
        # The 's?' makes the plural 's' optional, so "print" matches both "print" and "prints"
        # Examples:
        #  - 'miniature' -> 'miniature' ✓
        #  - "painting - oil on canvas" -> "painting" ✓
        #  - "prints and drawings" -> "print" + "drawing" ✓
        #  - "blueprint" -> no match (avoids false positive for "print") ✓
        #  - "combustion" -> no match (avoids false positive for "bust") ✓
        for searchable_work_type in SEARCHABLE_WORK_TYPES:
            pattern = rf"\b{re.escape(searchable_work_type)}s?\b"
            if re.search(pattern, work_type):
                searchable_work_types.add(searchable_work_type)
    return list(searchable_work_types)


def safe_int_from_date(date_str: str) -> int | None:
    """
    Extract year as integer from date string, handling various formats gracefully.

    Examples:
    - "1650-01-01" -> 1650
    - "1650" -> 1650
    - "ca. 1650" -> 1650
    - "invalid" -> None
    """
    if not date_str:
        return None

    # Extract first 4-digit number from string
    match = re.search(r"\d{4}", str(date_str))
    if match:
        try:
            return int(match.group())
        except ValueError:
            pass
    return None
