from dataclasses import dataclass

EXAMPLE_QUERIES = [
    "Reading child",
    "Orientalism",
    "Blue dress",
    "Inside cathedral",
    "Ancient Rome",
    "War",
    "Music",
    "Raw meat",
    "Moonlight by the sea",
    "Martin Luther",
    "Fauvism",
    "Cubism",
    "Death",
    "Nature morte",
    "Winter landscape",
    "Woman by a window",
    "Ship in a storm",
    "Female sculture",
    "Painter",
]


@dataclass
class WorkType:
    id: int
    name: str
    name_plural: str
    dk_name: str
    count: int

    def __post_init__(self):
        self.name = self.name.lower()
        self.name_plural = self.name_plural.lower()
        self.dk_name = self.dk_name.lower()


# TODO: Avoid hardcoding the count
WORK_TYPES: dict[int, WorkType] = {
    0: WorkType(id=0, name="total", name_plural="total", dk_name="total", count=19027),
    1: WorkType(
        id=1, name="drawing", name_plural="drawings", dk_name="tegning", count=13795
    ),
    2: WorkType(
        id=2, name="painting", name_plural="paintings", dk_name="maleri", count=4610
    ),
    3: WorkType(
        id=3, name="gouache", name_plural="gouaches", dk_name="gouache", count=622
    ),
    4: WorkType(
        id=4, name="watercolor", name_plural="watercolors", dk_name="akvarel", count=393
    ),
    5: WorkType(id=5, name="bust", name_plural="busts", dk_name="buste", count=313),
    6: WorkType(
        id=6, name="aquatint", name_plural="aquatints", dk_name="akvatinte", count=280
    ),
    7: WorkType(
        id=7,
        name="altarpiece",
        name_plural="altarpieces",
        dk_name="altertavle (maleri)",
        count=5,
    ),
    8: WorkType(id=8, name="pastel", name_plural="pastels", dk_name="pastel", count=35),
    9: WorkType(
        id=9, name="miniature", name_plural="miniatures", dk_name="miniature", count=6
    ),
    10: WorkType(
        id=10, name="print", name_plural="prints", dk_name="grafik", count=280
    ),
}

# Order WORK_TYPES dict by worktype.count
WORK_TYPES = dict(
    sorted(WORK_TYPES.items(), key=lambda item: item[1].count, reverse=True)
)

# Assert id is equal to the key in WORK_TYPES
for id, work_type in WORK_TYPES.items():
    assert id == work_type.id
