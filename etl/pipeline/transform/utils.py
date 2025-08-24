import re
from artsearch.src.constants import WORK_TYPES_DICT, SEARCHABLE_WORK_TYPES


def get_searchable_work_types(work_types: list[str]) -> list[str]:
    """
    Given a list of original work types (not necessarily in English) for a given artwork,
    return a list of standardized searchable work types in English.

    Returns empty list if no searchable work types found (to handle gracefully).
    """
    searchable_work_types = set()
    for work_type in work_types:
        if work_type in WORK_TYPES_DICT:
            work_type_eng = WORK_TYPES_DICT[work_type]["eng_sing"]
            if work_type_eng in SEARCHABLE_WORK_TYPES:
                searchable_work_types.add(work_type_eng)
            for category in SEARCHABLE_WORK_TYPES:
                if category in work_type_eng:
                    searchable_work_types.add(category)
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
