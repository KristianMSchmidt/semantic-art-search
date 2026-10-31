SUPPORTED_MUSEUMS = [
    {
        "slug": "smk",
        "full_name": "Statens Museum for Kunst",
        "short_name": "SMK",
    },
    {
        "slug": "cma",
        "full_name": "Cleveland Museum of Art",
        "short_name": "Cleveland",
    },
    {
        "slug": "rma",
        "full_name": "Rijksmuseum",
        "short_name": "Rijksmuseum",
    },
    {
        "slug": "met",
        "full_name": "Metropolitan Museum of Art",
        "short_name": "The Met",
    },
    {
        "slug": "aic",
        "full_name": "Art Institute of Chicago",
        "short_name": "Art Institute of Chicago",
    },
    {
        "slug": "nga",
        "full_name": "National Gallery of Art, Washington",
        "short_name": "National Gallery of Art",
    },
]

# Derived lists used by art map (views + management command)
MUSEUM_SLUGS = [m["slug"] for m in SUPPORTED_MUSEUMS]
MUSEUM_NAMES = [m["full_name"] for m in SUPPORTED_MUSEUMS]
MUSEUM_SLUG_TO_INDEX = {slug: i for i, slug in enumerate(MUSEUM_SLUGS)}

# Art map work type labels and lookup
WORK_TYPE_LABELS = [
    "painting", "print", "drawing", "watercolor", "design",
    "bust", "pastel", "aquatint", "gouache", "miniature", "other",
]
WORK_TYPE_TO_INDEX = {wt: i for i, wt in enumerate(WORK_TYPE_LABELS)}
OTHER_WORK_TYPE_INDEX = WORK_TYPE_LABELS.index("other")

# Art map century groups, in time order ("undated" last). Slugs go in map URLs
CENTURY_SLUGS = [
    "before-1400", "1400s", "1500s", "1600s", "1700s", "1800s", "from-1900", "undated",
]
CENTURY_NAMES = [
    "Before 1400", "1400s", "1500s", "1600s", "1700s", "1800s", "1900s and later", "Undated",
]
UNDATED_CENTURY_INDEX = CENTURY_SLUGS.index("undated")
FIRST_CENTURY_YEAR = 1400  # start of the first group after "before-1400"


def get_century_index(start: int | None, end: int | None) -> int:
    """Art map century group of an artwork, by production start year (end if no start)."""
    year = start if start is not None else end
    if year is None:
        return UNDATED_CENTURY_INDEX
    return min(max((year - FIRST_CENTURY_YEAR) // 100 + 1, 0), UNDATED_CENTURY_INDEX - 1)
