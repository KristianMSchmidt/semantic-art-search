"""
Integration tests for NGA extraction and transformation pipeline.

Tests WHAT the pipeline should do (select, store and transform NGA open data),
not HOW it does it (implementation details).

NGA publishes its collection as large CSV files (~170 MB in total), so the real-data
test only fetches the CSV headers. The pipeline logic is tested with small fixture CSVs.
"""

import csv
import io
from pathlib import Path

import pytest
import requests

from artsearch.src.services.artwork_description.metadata_fetcher import (
    fetch_and_clean_metadata,
)
from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.extract.extractors import nga_extractor
from etl.pipeline.extract.extractors.nga_extractor import (
    BASE_URL,
    OBJECTS_FILE,
    PUBLISHED_IMAGES_FILE,
    iter_nga_records,
)
from etl.pipeline.extract.helpers.upsert_raw_data import store_raw_data
from etl.pipeline.transform.transform import transform_and_upsert


OBJECT_COLUMNS = [
    "objectid", "accessionnum", "title", "displaydate", "beginyear", "endyear",
    "medium", "attribution", "classification", "subclassification", "isvirtual",
    "provenancetext",
]  # fmt: skip
IMAGE_COLUMNS = [
    "uuid", "iiifurl", "viewtype", "sequence", "openaccess", "depictstmsobjectid",
    "assistivetext",
]  # fmt: skip


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return path


def make_object(objectid: str, **overrides) -> dict:
    return {
        "objectid": objectid,
        "accessionnum": f"1943.8.{objectid}",
        "title": f"Artwork {objectid}",
        "displaydate": "c. 1936",
        "beginyear": "1936",
        "endyear": "1937",
        "medium": "oil on canvas",
        "attribution": "Hans Baldung",
        "classification": "Painting",
        "isvirtual": "0",
        # Multiline field, as in the real data
        "provenancetext": "Sold to someone.\nThen given to NGA.",
        **overrides,
    }


def make_image(objectid: str, **overrides) -> dict:
    uuid = f"uuid-{objectid}-{overrides.get('sequence', '0')}"
    return {
        "uuid": uuid,
        "iiifurl": f"https://api.nga.gov/iiif/{uuid}",
        "viewtype": "primary",
        "sequence": "0",
        "openaccess": "1",
        "depictstmsobjectid": objectid,
        "assistivetext": "A painting of a ship in a storm.",
        **overrides,
    }


@pytest.fixture
def nga_csv_files(tmp_path) -> tuple[Path, Path]:
    """Fixture CSVs covering the cases the extractor must handle."""
    objects = [
        make_object("1"),  # Valid painting
        make_object("2", medium="tempera on panel"),  # Valid, multiple primary images
        make_object("3", classification="Sculpture"),  # Wrong classification
        make_object("4", isvirtual="1"),  # Virtual object
        make_object("5"),  # Image not open access
        make_object("6"),  # Only an alternate image
        make_object("7"),  # No image at all
        # Supported by the transformer, but not (yet) included in extraction
        make_object("8", classification="Print", medium="etching and aquatint"),
        make_object(
            "9",
            classification="Index of American Design",
            medium="watercolor, graphite, and gouache on paper",
        ),
    ]
    images = [
        make_image("1"),
        make_image("2", sequence="1"),
        make_image("2", sequence="0"),  # Lowest sequence should win
        make_image("3"),
        make_image("4"),
        make_image("5", openaccess="0"),
        make_image("6", viewtype="alternate"),
        make_image("8"),
        make_image("9"),
    ]
    return (
        write_csv(tmp_path / "objects.csv", OBJECT_COLUMNS, objects),
        write_csv(tmp_path / "published_images.csv", IMAGE_COLUMNS, images),
    )


@pytest.mark.integration
def test_nga_open_data_csv_schema():
    """
    Test that the real NGA open data CSVs still have the columns we depend on.

    Only the first few KB of each file are fetched (HTTP Range request).

    Potential bugs this could catch:
    - NGA renamed or removed columns
    - Files moved in the GitHub repository
    """
    required_columns = {
        OBJECTS_FILE: {
            "objectid", "accessionnum", "title", "displaydate", "beginyear", "endyear",
            "medium", "attribution", "classification", "subclassification", "isvirtual",
        },
        PUBLISHED_IMAGES_FILE: {
            "iiifurl", "viewtype", "sequence", "openaccess", "depictstmsobjectid",
        },
    }  # fmt: skip

    for file_name, columns in required_columns.items():
        response = requests.get(
            f"{BASE_URL}/{file_name}", headers={"Range": "bytes=0-4095"}, timeout=30
        )
        assert response.status_code in (200, 206), f"Could not fetch {file_name}"
        header = next(csv.reader(io.StringIO(response.text)))
        missing = columns - set(header)
        assert not missing, f"{file_name} is missing columns: {missing}"


@pytest.mark.integration
def test_iter_nga_records_filters_and_joins(nga_csv_files):
    """
    Test that only eligible artworks are selected, each joined with its primary image.

    Potential bugs this could catch:
    - Non open access (copyrighted) images being included
    - Wrong classifications (e.g. prints, while we only include paintings) or virtual objects being included
    - Alternate views used instead of primary images
    - Multiline CSV fields breaking parsing
    """
    objects_path, images_path = nga_csv_files

    records = {r["objectid"]: r for r in iter_nga_records(objects_path, images_path)}

    assert set(records) == {"1", "2"}
    assert records["2"]["image"]["sequence"] == "0", "Lowest sequence primary image should be used"
    assert records["1"]["provenancetext"] == "Sold to someone.\nThen given to NGA."


@pytest.mark.integration
@pytest.mark.django_db
def test_nga_store_and_transform(nga_csv_files):
    """
    Test that NGA records can be stored and transformed to TransformedData.

    Potential bugs this could catch:
    - Transformer not extracting required fields
    - Work types not mapped to searchable work types
    - Wrong IIIF URL construction
    - Update/create logic broken (idempotency)
    """
    objects_path, images_path = nga_csv_files

    for _ in range(2):  # Twice to check idempotency
        for record in iter_nga_records(objects_path, images_path):
            store_raw_data(
                museum_slug="nga",
                object_number=record["accessionnum"],
                raw_json=record,
                museum_db_id=record["objectid"],
            )
    assert MetaDataRaw.objects.filter(museum_slug="nga").count() == 2

    for raw_record in MetaDataRaw.objects.filter(museum_slug="nga"):
        assert transform_and_upsert(raw_record) == "created"

    painting = TransformedData.objects.get(museum_slug="nga", object_number="1943.8.1")
    assert painting.museum_db_id == "1"
    assert painting.title == "Artwork 1"
    assert painting.artists == ["Hans Baldung"]
    assert painting.production_date_start == 1936
    assert painting.production_date_end == 1937
    assert painting.period == "c. 1936"
    assert painting.searchable_work_types == ["painting"]
    assert painting.thumbnail_url == "https://api.nga.gov/iiif/uuid-1-0/full/!800,800/0/default.jpg"



@pytest.mark.integration
@pytest.mark.django_db
def test_nga_transform_supports_drawings_and_prints(nga_csv_files, monkeypatch):
    """
    Test that drawings and prints transform correctly, so they can be added to
    ALLOWED_CLASSIFICATIONS later without surprises.

    Potential bugs this could catch:
    - Work type mapping for not yet extracted classifications broken
    - Medium keywords (watercolor, gouache, aquatint) not mapped to searchable work types
    """
    monkeypatch.setattr(
        nga_extractor,
        "ALLOWED_CLASSIFICATIONS",
        {"Painting", "Drawing", "Print", "Index of American Design"},
    )
    objects_path, images_path = nga_csv_files

    for record in iter_nga_records(objects_path, images_path):
        store_raw_data(
            museum_slug="nga",
            object_number=record["accessionnum"],
            raw_json=record,
            museum_db_id=record["objectid"],
        )
    for raw_record in MetaDataRaw.objects.filter(museum_slug="nga"):
        assert transform_and_upsert(raw_record) == "created"

    rendering = TransformedData.objects.get(museum_slug="nga", object_number="1943.8.9")
    assert sorted(rendering.searchable_work_types) == ["drawing", "gouache", "watercolor"]

    print_ = TransformedData.objects.get(museum_slug="nga", object_number="1943.8.8")
    assert sorted(print_.searchable_work_types) == ["aquatint", "print"]


@pytest.mark.integration
@pytest.mark.django_db
def test_nga_description_metadata_comes_from_stored_raw_data(nga_csv_files):
    """
    Test that AI description metadata for NGA is read from stored raw data.

    NGA has no per-object metadata API, so the description service must not make HTTP calls.
    """
    objects_path, images_path = nga_csv_files
    record = next(iter_nga_records(objects_path, images_path))
    store_raw_data(
        museum_slug="nga",
        object_number=record["accessionnum"],
        raw_json=record,
        museum_db_id=record["objectid"],
    )

    metadata = fetch_and_clean_metadata("nga", record["accessionnum"], record["objectid"])

    assert metadata["title"] == "Artwork 1"
    assert metadata["image_description"] == "A painting of a ship in a storm."
    assert "objectid" not in metadata
    assert "provenancetext" not in metadata

    with pytest.raises(ValueError):
        fetch_and_clean_metadata("nga", "does-not-exist", "0")
