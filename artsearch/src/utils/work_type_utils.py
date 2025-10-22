from artsearch.src.constants.work_types import WORK_TYPES_DICT


def get_standardized_work_type(work_type: str) -> str:
    """
    Get work type in standarized (English) form. Ke
    """
    return WORK_TYPES_DICT.get(work_type, work_type).strip().lower()
