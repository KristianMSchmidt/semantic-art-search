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
