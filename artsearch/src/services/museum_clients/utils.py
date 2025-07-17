from artsearch.src.constants import WORK_TYPES_DICT, SEARCHABLE_WORK_TYPES


def get_searchle_work_types(work_types: list[str]) -> list[str]:
    """
    Given a list of original work types (not necessarily in English) for a given artwork,
    return a list of standardized searchable work types in English.
    """
    searchable_work_types = set()
    for work_type in work_types:
        work_type_eng = WORK_TYPES_DICT[work_type]["eng_sing"]
        if work_type_eng in SEARCHABLE_WORK_TYPES:
            searchable_work_types.add(work_type_eng)
        for category in SEARCHABLE_WORK_TYPES:
            if category in work_type_eng:
                searchable_work_types.add(category)
    assert any(searchable_work_types), "No searchable work types found"
    return list(searchable_work_types)
