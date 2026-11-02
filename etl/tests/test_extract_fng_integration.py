"""
Integration tests for Finnish National Gallery (FNG) extraction and transformation.

Tests WHAT the pipeline should do (select, store and transform FNG open data),
not HOW it does it (implementation details).

FNG publishes its collection as one large JSON dump (~29 MB gzipped), so the real-data
test only reads the start of it. The pipeline logic is tested with a small fixture dump.
"""

import gzip
import io
import json
from pathlib import Path

import pytest
import requests

from artsearch.src.services.artwork_description.metadata_fetcher import (
    fetch_and_clean_metadata,
)
from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.extract.extractors import fng_extractor
from etl.pipeline.extract.extractors.fng_extractor import (
    DUMP_URL,
    iter_fng_records,
    iter_json_array,
    store_raw_data_fng,
)
from etl.pipeline.transform.transform import transform_and_upsert


def make_image(image_id: int, **overrides) -> dict:
    sizes = ["25", "250", "500", "1000", "2000", "4000"]
    return {
        "id": image_id,
        "license": "CC0",
        "isRiaDisplayImage": True,
        "width": 2000,
        "height": 1500,
        "jpg": {size: f"/media-assets/1/jpg/{size}/{image_id}.jpg" for size in sizes},
        **overrides,
    }


def make_object(object_id: int, **overrides) -> dict:
    return {
        "objectId": object_id,
        "inventoryNumber": f"A I {object_id}",
        "category": {"categoryId": "artwork", "en": "artwork", "fi": "teos"},
        "classifications": [{"en": "painting", "fi": "maalaus", "sv": "målning"}],
        "title": {"en": f"Artwork {object_id}", "fi": f"Teos {object_id}", "sv": ""},
        "people": [
            {
                "firstName": "Albert",
                "familyName": "Edelfelt",
                "birthYear": 1854,
                "deathYear": 1905,
                "attribution": None,
                "role": {"en": "Artist", "fi": "taiteilija"},
            }
        ],
        "yearFrom": 1887,
        "yearTo": None,
        "datePrefix": None,
        "materials": [{"en": "oil"}, {"en": "canvas"}],
        "keywords": [{"en": "landscape", "fi": "maisema"}],
        "multimedia": [make_image(object_id * 10)],
        **overrides,
    }


PRINT = [{"en": "Japanese woodblock print"}, {"en": "graphic arts"}]

FIXTURE_OBJECTS = [
    make_object(1, datePrefix={"en": "circa", "fi": "noin"}),  # Valid painting
    make_object(  # Valid miniature: Finnish title only, workshop attribution, gouache
        2,
        classifications=[{"en": "miniature"}, {"en": "painting"}],
        title={"en": "", "fi": "Naisen muotokuva", "sv": ""},
        people=[
            {
                "firstName": "Peter Adolf",
                "familyName": "Hall",
                "attribution": {"en": "workshop", "fi": "työhuone"},
                "role": {"en": "Artist"},
            }
        ],
        materials=[{"en": "gouache on ivory"}],
        yearFrom=1780,
        yearTo=1790,
    ),
    make_object(3, classifications=PRINT, inventoryNumber="A II 841:3"),  # Valid print
    make_object(  # Display image is not the first image
        4,
        multimedia=[
            make_image(41, isRiaDisplayImage=False),
            make_image(42, isRiaDisplayImage=True),
        ],
    ),
    make_object(  # Sketchbook page
        5, category={"categoryId": "artwork", "en": "part of a work"}, classifications=[]
    ),
    make_object(6, classifications=[{"en": "drawing"}]),  # Drawing: not included
    make_object(  # Sketchbook
        7, classifications=[{"en": "painting"}, {"en": "sketch book"}]
    ),
    make_object(8, multimedia=[]),  # No image (in copyright)
    make_object(9, multimedia=[make_image(90, license="CC BY")]),  # Not CC0
    make_object(10, category={"categoryId": "letter", "en": "letter"}),  # Letter
    make_object(11, inventoryNumber=""),  # No inventory number
    make_object(12, inventoryNumber="A I 1"),  # Duplicate of object 1
    make_object(  # Unknown artist, dates equal to the lifespan (placeholder for undated)
        13,
        people=[
            {"firstName": None, "familyName": "tekijä ei tiedossa", "role": None},
        ],
    ),
    make_object(14, yearFrom=1854, yearTo=1905),  # Edelfelt's lifespan: undated
    make_object(15, yearFrom=None, yearTo=1890),  # Only an end year
    make_object(  # Artist and caster: the artist's lifespan still means undated
        16,
        yearFrom=1854,
        yearTo=1905,
        people=[
            {
                "firstName": "Albert",
                "familyName": "Edelfelt",
                "birthYear": 1854,
                "deathYear": 1905,
                "role": {"en": "Artist"},
            },
            {"familyName": "Some Foundry", "birthYear": 1900, "role": {"en": "Caster"}},
        ],
    ),
]


@pytest.fixture
def fng_dump(tmp_path) -> Path:
    """A gzipped fixture dump, as the FNG server sends it."""
    path = tmp_path / "objects.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(FIXTURE_OBJECTS, f, indent=2, ensure_ascii=False)
    return path


def store_fixture_dump(fng_dump: Path, monkeypatch) -> None:
    monkeypatch.setattr(fng_extractor, "download_dump", lambda dest_dir: fng_dump)
    store_raw_data_fng()


@pytest.mark.unit
@pytest.mark.parametrize("chunk_size", [1, 7, 64, 1024 * 1024])
def test_iter_json_array_matches_json_load(chunk_size):
    """
    Test that streaming the dump gives the same items as loading it at once.

    Potential bugs this could catch:
    - Items cut off at chunk boundaries (strings, numbers, nested objects)
    - Separators or brackets inside strings mistaken for array syntax
    """
    items = [
        {"a": "text with ] and , and [ inside", "n": 12345, "nested": {"x": [1, 2]}},
        123456789,
        "string",
        [],
        {"unicode": "Äänekoski – målning"},
        1.5,
    ]
    text = json.dumps(items, indent=2, ensure_ascii=False)

    assert list(iter_json_array(io.StringIO(text), chunk_size=chunk_size)) == items
    assert list(iter_json_array(io.StringIO("[]"), chunk_size=chunk_size)) == []


@pytest.mark.unit
def test_iter_json_array_rejects_truncated_or_malformed_dump(monkeypatch):
    """A cut-off or malformed download must fail loudly, not store a partial collection."""
    with pytest.raises(ValueError):
        list(iter_json_array(io.StringIO('[{"a": 1}, {"b": '), chunk_size=4))
    with pytest.raises(ValueError):
        list(iter_json_array(io.StringIO('[{"a": 1} x]'), chunk_size=4))

    # Malformed data must not make it buffer the rest of the file
    monkeypatch.setattr(fng_extractor, "MAX_ITEM_CHARS", 100)
    malformed = '[{"a": 1}, {"b": oops, "c": "' + "x" * 1000 + '"}]'
    with pytest.raises(ValueError, match="No complete JSON item"):
        list(iter_json_array(io.StringIO(malformed), chunk_size=10))


@pytest.mark.integration
def test_fng_dump_schema():
    """
    Test that the real FNG dump still has the fields we depend on.

    Only the start of the dump is read (the download is closed early).

    Potential bugs this could catch:
    - FNG moved the dump or put it behind an API key
    - FNG renamed or removed fields
    """
    with requests.get(DUMP_URL, stream=True, timeout=60) as response:
        response.raise_for_status()
        data = b""
        for chunk in response.iter_content(64 * 1024):
            data += chunk
            if len(data) > 256 * 1024:
                break
    text = data.decode("utf-8", errors="ignore")

    items = []
    try:
        for item in iter_json_array(io.StringIO(text)):
            items.append(item)
    except ValueError:
        pass  # Expected: the text is cut off
    assert len(items) >= 5, "Could not parse the start of the dump"

    # "title", "yearFrom" etc. are optional: not every object has them
    required_fields = {
        "objectId", "inventoryNumber", "category", "classifications", "people",
        "materials", "multimedia",
    }  # fmt: skip
    for item in items:
        missing = required_fields - set(item)
        assert not missing, f"Object {item.get('objectId')} is missing fields: {missing}"

    images = [m for item in items for m in item["multimedia"]]
    assert images, "No images in the first objects"
    for image in images:
        assert {"license", "jpg", "isRiaDisplayImage"} <= set(image)
        assert {"1000", "4000"} <= set(image["jpg"])


@pytest.mark.integration
def test_iter_fng_records_filters(fng_dump):
    """
    Test that only eligible artworks are selected, each with its CC0 display image.

    Potential bugs this could catch:
    - Sketchbook pages, letters, drawings or sketchbooks being included
    - In-copyright works (no CC0 image) being included
    - The wrong image used when an object has several
    """
    records = {r["objectId"]: r for r in iter_fng_records(fng_dump)}

    assert set(records) == {1, 2, 3, 4, 12, 13, 14, 15, 16}
    assert records[4]["image"]["id"] == 42, "The display image should be used"
    assert "multimedia" not in records[4], "Only the chosen image should be stored"


@pytest.mark.integration
@pytest.mark.django_db
def test_fng_store_and_transform(fng_dump, monkeypatch):
    """
    Test that FNG records can be stored and transformed to TransformedData.

    Potential bugs this could catch:
    - Duplicate inventory numbers stored twice
    - Transformer not extracting required fields
    - Work types not mapped to searchable work types
    - Wrong image URL construction
    - Update/create logic broken (idempotency)
    """
    for _ in range(2):  # Twice to check idempotency
        store_fixture_dump(fng_dump, monkeypatch)
    raw = MetaDataRaw.objects.filter(museum_slug="fng")
    assert sorted(raw.values_list("object_number", flat=True)) == [
        "A I 1", "A I 13", "A I 14", "A I 15", "A I 16", "A I 2", "A I 4", "A II 841:3",
    ]  # fmt: skip
    assert raw.get(object_number="A I 1").museum_db_id == "1", "First occurrence wins"

    for raw_record in raw:
        assert transform_and_upsert(raw_record) == "created"

    painting = TransformedData.objects.get(museum_slug="fng", object_number="A I 1")
    assert painting.museum_db_id == "1"
    assert painting.title == "Artwork 1"
    assert painting.artists == ["Albert Edelfelt"]
    assert painting.production_date_start == 1887
    assert painting.production_date_end == 1887
    assert painting.period == "circa 1887"
    assert painting.searchable_work_types == ["painting"]
    base = "https://kokoelma.kansallisgalleria.fi/media-assets/1/jpg"
    assert painting.thumbnail_url == f"{base}/1000/10.jpg"
    assert painting.image_url == f"{base}/4000/10.jpg"

    miniature = TransformedData.objects.get(museum_slug="fng", object_number="A I 2")
    assert miniature.title == "Naisen muotokuva"
    assert miniature.artists == ["Workshop of Peter Adolf Hall"]
    assert miniature.period == "1780–1790"
    assert sorted(miniature.searchable_work_types) == ["gouache", "miniature", "painting"]

    woodblock = TransformedData.objects.get(museum_slug="fng", object_number="A II 841:3")
    assert woodblock.searchable_work_types == ["print"]

    unknown = TransformedData.objects.get(museum_slug="fng", object_number="A I 13")
    assert unknown.artists == []

    undated = TransformedData.objects.get(museum_slug="fng", object_number="A I 14")
    assert undated.production_date_start is None
    assert undated.production_date_end is None
    assert undated.period is None

    end_year_only = TransformedData.objects.get(museum_slug="fng", object_number="A I 15")
    assert (end_year_only.production_date_start, end_year_only.production_date_end) == (1890, 1890)

    with_caster = TransformedData.objects.get(museum_slug="fng", object_number="A I 16")
    assert with_caster.artists == ["Albert Edelfelt"], "Casters are not artists"
    assert with_caster.production_date_start is None


@pytest.mark.integration
@pytest.mark.django_db
def test_fng_description_metadata_comes_from_stored_raw_data(fng_dump, monkeypatch):
    """
    Test that AI description metadata for FNG is read from stored raw data.

    FNG's per-object API needs a key, so the description service must not make HTTP calls.
    """
    store_fixture_dump(fng_dump, monkeypatch)

    metadata = fetch_and_clean_metadata("fng", "A I 2", "2")

    assert metadata["title_finnish"] == "Naisen muotokuva"
    assert metadata["artists"] == [
        {"name": "Peter Adolf Hall", "role": "Artist", "attribution": "workshop"}
    ]
    assert metadata["classifications"] == ["miniature", "painting"]
    assert metadata["materials"] == ["gouache on ivory"]
    assert "multimedia" not in metadata
    assert "image" not in metadata

    unknown = fetch_and_clean_metadata("fng", "A I 13", "13")
    assert unknown["artists"] == [{"name": "unknown"}], "Placeholder name must not reach the LLM"

    with pytest.raises(ValueError):
        fetch_and_clean_metadata("fng", "does-not-exist", "0")
