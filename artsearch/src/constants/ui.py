EXAMPLE_QUERIES: dict[str, list[str]] = {
    "chosen": [
        "Ship in a storm",
        "Reading child",
        "Orientalism",
        "Ancient Rome",
        "Inside cathedral",
        "War",
        "Music",
        "Moonlight by the sea",
        "Fauvism",
        "Cubism",
        "Blue dress",
        "Death",
        "Elephant",
        "Hindu deity",
        "Painter",
        "Male model",
        "Fish still life",
        "Winter landscape",
        "Colorful flowers in a vase",
        "Crucifixion",
        "Calligraphy and landscape",
        "Human anatomy",
        "Mourning",
    ],
    "candidates": [
        "Breastfeeding",
        "Buddha",
        "Dead birds",
        "Bible scene",
        "Persian carpet",
        "Camel",
        "Rembrandt",
        "Martin Luther",
        "Windmill",
        "Map of a fortress",
    ],
}

# Responsive breakpoint counts for visible example queries
EXAMPLE_QUERY_COUNTS = {
    "sm": 5,  # < 768px
    "md": 5,  # 768px - 1023px
    "lg": 5,  # >= 1024px
}
