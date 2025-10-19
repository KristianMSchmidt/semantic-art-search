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

        # Direct match
        if work_type in SEARCHABLE_WORK_TYPES:
            searchable_work_types.add(work_type)
            continue

        # Partial matches
        #  - "painting - oil on canvas" -> "painting",
        #  - "prints" -> "print",
        #  - "prints and drawings" -> "print" + "drawing"
        for searchable_work_type in SEARCHABLE_WORK_TYPES:
            if searchable_work_type in work_type:
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
