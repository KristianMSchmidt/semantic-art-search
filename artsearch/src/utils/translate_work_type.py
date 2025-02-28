from artsearch.src.constants import WORK_TYPES


def work_type_to_english(work_type_name_danish: str) -> str:
    """
    Translates the Danish name of awork type to English.
    """
    for work_type in WORK_TYPES.values():
        if work_type.dk_name.lower() == work_type_name_danish.lower():
            return work_type.name
    return work_type_name_danish
