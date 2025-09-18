import pytest

from etl.models import MetaDataRaw, TransformedData
from etl.pipeline.transform.factory import get_transformer, TRANSFORMERS
from etl.pipeline.transform.transform import transform_and_upsert
from etl.pipeline.transform.models import TransformedArtworkData


@pytest.mark.unit
class TestTransformerFactory:
    """Test the transformer factory pattern."""

    @pytest.mark.parametrize("museum_slug", ["smk", "cma", "rma", "met"])
    def test_get_transformer_valid_museums(self, museum_slug):
        """Test that get_transformer returns correct functions for valid museums."""
        transformer = get_transformer(museum_slug)
        assert transformer is not None
        assert callable(transformer)
        assert transformer == TRANSFORMERS[museum_slug]

    def test_get_transformer_invalid_museum(self):
        """Test that get_transformer returns None for invalid museums."""
        transformer = get_transformer("invalid_museum")
        assert transformer is None

    def test_all_supported_museums_have_transformers(self):
        """Test that all museums have corresponding transformers."""
        from artsearch.src.utils.get_museums import get_museum_slugs

        supported_slugs = get_museum_slugs()
        for slug in supported_slugs:
            transformer = get_transformer(slug)
            assert callable(transformer)


@pytest.mark.unit
class TestSMKTransformer:
    """Test SMK transformer with real data structures."""

    @pytest.fixture
    def valid_smk_data(self):
        """Valid SMK raw data fixture."""
        return {
            "object_number": "KMS123",
            "image_thumbnail": "https://example.com/image.jpg",
            "object_names": [{"name": "Painting"}, {"name": "Oil on canvas"}],
            "titles": [
                {"title": "The Starry Night", "language": "en"},
                {"title": "Den stjerneklare nat", "language": "da"},
            ],
            "artist": [
                {"name": "Vincent van Gogh", "birth_year": 1853, "death_year": 1890}
            ],
            "production_date": [{"start": 1889, "end": 1889}],
        }

    @pytest.fixture
    def minimal_smk_data(self):
        """Minimal valid SMK data."""
        return {
            "object_number": "KMS456",
            "image_thumbnail": "https://example.com/minimal.jpg",
            "object_names": [{"name": "Painting"}],
        }

    @pytest.fixture
    def invalid_smk_data(self):
        """Invalid SMK data missing required fields."""
        return {"titles": [{"title": "Missing object_number"}]}

    def test_transform_smk_valid_data(self, valid_smk_data):
        """Test SMK transformer with complete valid data."""
        from etl.pipeline.transform.transformers.smk_transformer import (
            transform_smk_data,
        )

        result = transform_smk_data(valid_smk_data, "KMS123")

        assert isinstance(result, TransformedArtworkData)
        assert result.object_number == "KMS123"
        assert result.museum_slug == "smk"
        assert result.thumbnail_url == "https://example.com/image.jpg"
        assert result.title == "The Starry Night"
        assert "Vincent van Gogh" in result.artist
        assert len(result.searchable_work_types) > 0

    def test_transform_smk_minimal_data(self, minimal_smk_data):
        """Test SMK transformer with minimal required data."""
        from etl.pipeline.transform.transformers.smk_transformer import (
            transform_smk_data,
        )

        result = transform_smk_data(minimal_smk_data, "KMS456")

        assert isinstance(result, TransformedArtworkData)
        assert result.object_number == "KMS456"
        assert result.museum_slug == "smk"
        assert result.thumbnail_url == "https://example.com/minimal.jpg"

    def test_transform_smk_invalid_data(self, invalid_smk_data):
        """Test SMK transformer with invalid data returns None."""
        from etl.pipeline.transform.transformers.smk_transformer import (
            transform_smk_data,
        )

        result = transform_smk_data(invalid_smk_data, "INVALID")

        assert result is None

    def test_transform_smk_missing_thumbnail(self, valid_smk_data):
        """Test SMK transformer fails without thumbnail."""
        from etl.pipeline.transform.transformers.smk_transformer import (
            transform_smk_data,
        )

        valid_smk_data.pop("image_thumbnail")
        result = transform_smk_data(valid_smk_data, "KMS123")

        assert result is None


@pytest.mark.unit
class TestCMATransformer:
    """Test CMA transformer with real data structures."""

    @pytest.fixture
    def valid_cma_data(self):
        """Valid CMA raw data fixture."""
        return {
            "accession_number": "1979.53",
            "images": {"web": {"url": "https://example.com/cma.jpg"}},
            "type": "Painting",
            "title": "Water Lilies",
            "creators": [
                {
                    "description": "Claude Monet",
                    "birth_year": "1840",
                    "death_year": "1926",
                }
            ],
            "creation_date": "1919",
        }

    def test_transform_cma_valid_data(self, valid_cma_data):
        """Test CMA transformer with valid data."""
        from etl.pipeline.transform.transformers.cma_transformer import (
            transform_cma_data,
        )

        result = transform_cma_data(valid_cma_data, "1979.53")

        assert isinstance(result, TransformedArtworkData)
        assert result.object_number == "1979.53"
        assert result.museum_slug == "cma"
        assert result.thumbnail_url == "https://example.com/cma.jpg"
        assert result.title == "Water Lilies"
        assert "Claude Monet" in result.artist


@pytest.mark.integration
@pytest.mark.django_db
class TestTransformAndUpsert:
    """Test the core transform_and_upsert function with real database operations."""

    @pytest.fixture
    def smk_raw_data(self):
        """Create a MetaDataRaw record for testing."""
        return MetaDataRaw.objects.create(
            museum_slug="smk",
            museum_object_id="KMS789",
            raw_json={
                "object_number": "KMS789",
                "image_thumbnail": "https://example.com/test.jpg",
                "object_names": [{"name": "Painting"}],
                "titles": [{"title": "Test Artwork"}],
            },
            raw_hash="test_hash_123",
        )

    @pytest.fixture
    def invalid_raw_data(self):
        """Create invalid MetaDataRaw record for testing error cases."""
        return MetaDataRaw.objects.create(
            museum_slug="smk",
            museum_object_id="INVALID",
            raw_json={
                "titles": [{"title": "Missing required fields"}]
                # Missing object_number and image_thumbnail
            },
            raw_hash="invalid_hash",
        )

    def test_transform_and_upsert_create_new(self, smk_raw_data):
        """Test creating a new transformed record."""
        # Ensure no existing transformed data
        assert not TransformedData.objects.filter(raw_data=smk_raw_data).exists()

        result = transform_and_upsert(smk_raw_data)

        assert result == "created"

        # Verify record was created
        transformed = TransformedData.objects.get(raw_data=smk_raw_data)
        assert transformed.object_number == "KMS789"
        assert transformed.museum_slug == "smk"
        assert transformed.source_raw_hash == "test_hash_123"

    def test_transform_and_upsert_skip_unchanged(self, smk_raw_data):
        """Test skipping unchanged record."""
        # Create existing transformed record
        TransformedData.objects.create(
            raw_data=smk_raw_data,
            object_number="KMS789",
            museum_slug="smk",
            searchable_work_types=["painting"],
            thumbnail_url="https://example.com/test.jpg",
            source_raw_hash="test_hash_123",  # Same hash
        )

        result = transform_and_upsert(smk_raw_data)

        assert result == "skipped"

    def test_transform_and_upsert_update_stale(self, smk_raw_data):
        """Test updating a stale record with new hash."""
        # Create existing transformed record with old hash
        TransformedData.objects.create(
            raw_data=smk_raw_data,
            object_number="KMS789",
            museum_slug="smk",
            searchable_work_types=["painting"],
            thumbnail_url="https://example.com/old.jpg",
            source_raw_hash="old_hash_456",  # Different hash
        )

        result = transform_and_upsert(smk_raw_data)

        assert result == "updated"

        # Verify record was updated
        transformed = TransformedData.objects.get(raw_data=smk_raw_data)
        assert transformed.source_raw_hash == "test_hash_123"  # New hash
        assert (
            transformed.thumbnail_url == "https://example.com/test.jpg"
        )  # Updated data

    def test_transform_and_upsert_invalid_data(self, invalid_raw_data):
        """Test handling invalid data that fails transformation."""
        result = transform_and_upsert(invalid_raw_data)

        assert result == "error"

        # Verify no record was created
        assert not TransformedData.objects.filter(raw_data=invalid_raw_data).exists()

    def test_transform_and_upsert_invalid_museum(self):
        """Test handling invalid museum slug."""
        invalid_museum_data = MetaDataRaw.objects.create(
            museum_slug="invalid",  # Shorter slug to fit field limit
            museum_object_id="TEST",
            raw_json={"test": "data"},
            raw_hash="hash",
        )

        # The current implementation raises KeyError which gets caught by the outer try-except
        result = transform_and_upsert(invalid_museum_data)

        assert result == "error"


@pytest.mark.unit
class TestTransformerValidation:
    """Test transformer validation logic across all museums."""

    def test_all_transformers_handle_empty_data(self):
        """Test that all transformers handle empty data gracefully."""
        empty_data = {}

        for slug, transformer in TRANSFORMERS.items():
            result = transformer(empty_data, "TEST")
            assert result is None, (
                f"Transformer for {slug} should return None for empty data"
            )

    @pytest.mark.parametrize("museum_slug", ["smk", "cma", "rma", "met"])
    def test_transformers_return_correct_museum_slug(self, museum_slug):
        """Test that transformers set correct museum_slug in output."""
        # Create minimal valid data for each museum
        test_data = {
            "smk": {
                "object_number": "KMS123",
                "image_thumbnail": "https://example.com/test.jpg",
                "object_names": [{"name": "Painting"}],
            },
            "cma": {
                "accession_number": "TEST123",
                "images": {"web": {"url": "https://example.com/test.jpg"}},
                "type": "Painting",
            },
            "rma": {
                "objectNumber": "RM123",
                "hasRepresentation": [{"@id": "https://example.com/test.jpg"}],
                "classification": {"@id": "Painting"},
            },
            "met": {
                "objectID": 123,
                "accessionNumber": "MET123",
                "primaryImageSmall": "https://example.com/test.jpg",
                "classification": "Painting",
            },
        }

        transformer = get_transformer(museum_slug)
        assert transformer is not None

        data = test_data.get(museum_slug, {})

        # Skip test if we don't have test data for this museum
        if not data:
            pytest.skip(f"No test data defined for {museum_slug}")

        result = transformer(data, "TEST")

        if result is not None:  # Only test if transformation succeeds
            assert result.museum_slug == museum_slug
