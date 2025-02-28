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

    def __post_init__(self):
        self.name = self.name.lower()
        self.name_plural = self.name_plural.lower()
        self.dk_name = self.dk_name.lower()


WORK_TYPES: dict[int, WorkType] = {
    1: WorkType(id=1, name="painting", name_plural="paintings", dk_name="maleri"),
    2: WorkType(id=2, name="drawing", name_plural="drawings", dk_name="tegning"),
    3: WorkType(id=3, name="aquatint", name_plural="aquatints", dk_name="akvatinte"),
    4: WorkType(id=4, name="watercolor", name_plural="watercolors", dk_name="akvarel"),
    5: WorkType(
        id=5,
        name="altarpiece",
        name_plural="altarpieces",
        dk_name="altertavle (maleri)",
    ),
    6: WorkType(id=6, name="bust", name_plural="busts", dk_name="buste"),
    7: WorkType(id=7, name="pastel", name_plural="pastels", dk_name="pastel"),
    8: WorkType(id=8, name="miniature", name_plural="miniatures", dk_name="miniature"),
}
