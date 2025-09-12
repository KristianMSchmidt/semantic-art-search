import pytest  # type: ignore
from unittest.mock import Mock, patch

from etl.models import MetaDataRaw
from etl.pipeline.extract.factory import get_extractor, EXTRACTORS
from etl.pipeline.extract.helpers.upsert_raw_data import (
    store_raw_data,
    compute_hash_of_json,
)


@pytest.mark.unit
class TestExtractorFactory:
    """Test the extractor factory pattern."""

    @pytest.mark.parametrize("museum_slug", ["smk", "cma", "rma", "met"])
    def test_get_extractor_valid_museums(self, museum_slug):
        """Test that get_extractor returns correct functions for valid museums."""
        extractor = get_extractor(museum_slug)
        assert extractor is not None
        assert callable(extractor)
        assert extractor == EXTRACTORS[museum_slug]

    def test_get_extractor_invalid_museum(self):
        """Test that get_extractor raises ValueError for invalid museums."""
        with pytest.raises(ValueError, match="Unsupported museum slug"):
            get_extractor("invalid_museum")

    def test_all_supported_museums_have_extractors(self):
        """Test that all museums in SUPPORTED_MUSEUMS have corresponding extractors."""
        from artsearch.src.utils.get_museums import get_museum_slugs

        supported_slugs = get_museum_slugs()
        for slug in supported_slugs:
            # Should not raise an exception
            extractor = get_extractor(slug)
            assert callable(extractor)


@pytest.mark.unit
@pytest.mark.django_db
class TestStoreRawData:
    """Test the store_raw_data utility function."""

    @pytest.fixture
    def test_data(self):
        """Test data fixture."""
        return {
            "id": 12345,
            "title": "Test Artwork",
            "artist": "Test Artist",
            "date": "2023",
        }

    @pytest.fixture
    def museum_slug(self):
        return "test"

    @pytest.fixture
    def object_id(self):
        return "TEST123"

    def test_compute_hash_of_json_consistency(self, test_data):
        """Test that hash computation is consistent."""
        hash1 = compute_hash_of_json(test_data)
        hash2 = compute_hash_of_json(test_data)
        assert hash1 == hash2

    def test_compute_hash_of_json_different_data(self):
        """Test that different data produces different hashes."""
        data1 = {"a": 1, "b": 2}
        data2 = {"a": 1, "b": 3}
        hash1 = compute_hash_of_json(data1)
        hash2 = compute_hash_of_json(data2)
        assert hash1 != hash2

    def test_store_raw_data_new_record(self, museum_slug, object_id, test_data):
        """Test storing new raw data creates a record."""
        changed = store_raw_data(museum_slug, object_id, test_data)

        assert changed is True

        # Verify record was created
        record = MetaDataRaw.objects.get(
            museum_slug=museum_slug, museum_object_id=object_id
        )
        assert record.raw_json == test_data
        assert record.raw_hash == compute_hash_of_json(test_data)

    def test_store_raw_data_duplicate_no_change(
        self, museum_slug, object_id, test_data
    ):
        """Test that storing identical data returns False (no change)."""
        # Store initial data
        store_raw_data(museum_slug, object_id, test_data)

        # Store same data again
        changed = store_raw_data(museum_slug, object_id, test_data)

        assert changed is False

        # Verify only one record exists
        count = MetaDataRaw.objects.filter(
            museum_slug=museum_slug, museum_object_id=object_id
        ).count()
        assert count == 1

    def test_store_raw_data_update_existing(self, museum_slug, object_id, test_data):
        """Test that storing modified data updates the record."""
        # Store initial data
        store_raw_data(museum_slug, object_id, test_data)

        # Modify data
        modified_data = test_data.copy()
        modified_data["title"] = "Modified Title"

        # Store modified data
        changed = store_raw_data(museum_slug, object_id, modified_data)

        assert changed is True

        # Verify record was updated
        record = MetaDataRaw.objects.get(
            museum_slug=museum_slug, museum_object_id=object_id
        )

        assert record.raw_json == modified_data
        assert record.raw_hash == compute_hash_of_json(modified_data)


@pytest.mark.integration
@pytest.mark.django_db
class TestExtractorIntegration:
    """Integration tests with mocked API calls."""

    @patch("requests.Session.get")
    def test_met_extractor_basic_flow(self, mock_get):
        """Test MET extractor with mocked API responses."""
        # Mock department API response
        dept_response = Mock()
        dept_response.json.return_value = {"objectIDs": [1, 2, 3]}
        dept_response.raise_for_status = Mock()

        # Mock search API response
        search_response = Mock()
        search_response.json.return_value = {"objectIDs": [4, 5, 6]}
        search_response.raise_for_status = Mock()

        # Mock individual object API responses
        object_response = Mock()
        object_response.json.return_value = {
            "objectID": 1,
            "title": "Test Artwork",
            "artistDisplayName": "Test Artist",
            "isPublicDomain": True,
            "primaryImageSmall": "http://example.com/image.jpg",
        }
        object_response.raise_for_status = Mock()

        # Configure mock to return different responses based on URL
        def side_effect(url, *_args, **_kwargs):
            if "departmentIds" in url:
                return dept_response
            elif "search" in url:
                return search_response
            else:
                return object_response

        mock_get.side_effect = side_effect

        # Import and run specific extractor functions
        from etl.pipeline.extract.extractors.met_extractor import (
            get_dept_object_ids,
            get_object_ids_by_search,
            get_item,
        )

        # Test department object IDs fetch
        import requests

        session = requests.Session()
        dept_ids = get_dept_object_ids(11, session)
        assert dept_ids == [1, 2, 3]

        # Test search object IDs fetch
        search_ids = get_object_ids_by_search({"q": "test"}, session)
        assert search_ids == [4, 5, 6]

        # Test individual item fetch
        item = get_item(1, session)
        assert item["objectID"] == 1
        assert item["title"] == "Test Artwork"

    @patch("requests.Session.get")
    def test_smk_extractor_basic_flow(self, mock_get):
        """Test SMK extractor with mocked API responses."""
        # Mock SMK API response
        smk_response = Mock()
        smk_response.json.return_value = {
            "found": 2,
            "items": [
                {
                    "id": "KMS1",
                    "titles": [{"title": "Test SMK Artwork 1"}],
                    "artist": "Test Artist 1",
                    "object_number": "KMS1",
                    "image_thumbnail": "http://example.com/smk1.jpg",
                },
                {
                    "id": "KMS2",
                    "titles": [{"title": "Test SMK Artwork 2"}],
                    "artist": "Test Artist 2",
                    "object_number": "KMS2",
                    "image_thumbnail": "http://example.com/smk2.jpg",
                },
            ],
        }
        smk_response.raise_for_status = Mock()
        mock_get.return_value = smk_response

        # Test SMK API fetch function
        from etl.pipeline.extract.extractors.smk_extractor import (
            fetch_raw_data_from_smk_api,
        )
        import requests

        session = requests.Session()
        result = fetch_raw_data_from_smk_api({"keys": "*"}, session)

        # Verify response structure
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == "KMS1"
        assert result["items"][0]["titles"][0]["title"] == "Test SMK Artwork 1"

    @patch("requests.Session.get")
    def test_cma_extractor_basic_flow(self, mock_get):
        """Test CMA extractor with mocked API responses."""
        # Mock CMA API response
        cma_response = Mock()
        cma_response.json.return_value = {
            "info": {"total": 2},
            "data": [
                {
                    "id": 1,
                    "title": "Test CMA Artwork 1",
                    "creators": [{"description": "Test Artist 1"}],
                    "accession_number": "CMA1",
                    "images": {"web": {"url": "http://example.com/cma1.jpg"}},
                },
                {
                    "id": 2,
                    "title": "Test CMA Artwork 2",
                    "creators": [{"description": "Test Artist 2"}],
                    "accession_number": "CMA2",
                    "images": {"web": {"url": "http://example.com/cma2.jpg"}},
                },
            ],
        }
        cma_response.raise_for_status = Mock()
        mock_get.return_value = cma_response

        # Test CMA API fetch function
        from etl.pipeline.extract.extractors.cma_extractor import (
            fetch_raw_data_from_cma_api,
        )
        import requests

        session = requests.Session()
        result = fetch_raw_data_from_cma_api({"q": "", "has_image": 1}, session)

        # Verify response structure
        assert result["total_count"] == 2
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == 1
        assert result["items"][0]["title"] == "Test CMA Artwork 1"

    @patch("requests.Session.get")
    def test_rma_extractor_basic_flow(self, mock_get):
        """Test RMA extractor with mocked API responses."""
        # Mock RMA search API response
        search_response = Mock()
        search_response.json.return_value = {
            "partOf": {"totalItems": 2},
            "orderedItems": [
                {"id": "https://id.rijksmuseum.nl/RMA-1"},
                {"id": "https://id.rijksmuseum.nl/RMA-2"},
            ],
        }
        search_response.raise_for_status = Mock()

        # Mock RMA record fetch API response (XML)
        record_response = Mock()
        record_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <OAI-PMH>
            <GetRecord>
                <record>
                    <header>
                        <identifier>RMA-1</identifier>
                    </header>
                    <metadata>
                        <title>Test RMA Artwork</title>
                        <creator>Test Artist</creator>
                    </metadata>
                </record>
            </GetRecord>
        </OAI-PMH>"""
        record_response.raise_for_status = Mock()

        def side_effect(url, *args, **kwargs):
            if "search/collection" in url:
                return search_response
            else:
                return record_response

        mock_get.side_effect = side_effect

        # Test RMA API fetch functions
        from etl.pipeline.extract.extractors.rma_extractor import (
            fetch_raw_data_from_rma_api,
            fetch_record,
        )
        import requests

        session = requests.Session()

        # Test search function
        search_result = fetch_raw_data_from_rma_api({}, session)
        assert search_result["total_count"] == 2
        assert len(search_result["items"]) == 2

        # Test individual record fetch
        record = fetch_record("RMA-1", session)
        assert "header" in record
        assert "metadata" in record
        assert record["header"]["identifier"] == "RMA-1"

    def test_filter_recent_objects_logic(self):
        """Test the logic of filter_recent_objects function (simplified)."""

        # Create a record that should be old enough to be included
        # We just test that records exist and get processed correctly
        MetaDataRaw.objects.create(
            museum_slug="met",
            museum_object_id="100",
            raw_json={"test": "data"},
            raw_hash="hash1",
        )

        # Test basic functionality - all new records should be filtered out since they were just created
        from etl.pipeline.extract.extractors.met_extractor import filter_recent_objects

        object_ids = [100, 999]  # 100 exists (recent), 999 doesn't exist
        filtered = filter_recent_objects(object_ids)

        # Since we just created object 100, it should be filtered out as recent
        # Object 999 doesn't exist so should be included for fetching
        assert 999 in filtered
        # Object 100 should be filtered out since it's recent
        assert 100 not in filtered

        # Test with no objects
        empty_filtered = filter_recent_objects([])
        assert empty_filtered == []


@pytest.mark.unit
class TestExtractOrchestration:
    """Test the main extract orchestration functions."""

    @patch("etl.pipeline.extract.extract.get_extractor")
    @patch("etl.pipeline.extract.extract.get_museum_slugs")
    def test_run_extract_all_museums(self, mock_get_museum_slugs, mock_get_extractor):
        """Test running extraction for all museums."""
        from etl.pipeline.extract.extract import run_extract

        # Mock the museum slugs and extractors
        mock_get_museum_slugs.return_value = ["smk", "cma"]
        mock_extractor = Mock()
        mock_get_extractor.return_value = mock_extractor

        # Run extraction
        run_extract()

        # Verify all museums were processed
        assert mock_get_extractor.call_count == 2
        mock_get_extractor.assert_any_call("smk")
        mock_get_extractor.assert_any_call("cma")

        # Verify extractors were called
        assert mock_extractor.call_count == 2

    @patch("etl.pipeline.extract.extract.get_extractor")
    def test_run_extract_specific_museums(self, mock_get_extractor):
        """Test running extraction for specific museums."""
        from etl.pipeline.extract.extract import run_extract

        mock_extractor = Mock()
        mock_get_extractor.return_value = mock_extractor

        # Run extraction for specific museums
        run_extract(["met", "rma"])

        # Verify only specified museums were processed
        assert mock_get_extractor.call_count == 2
        mock_get_extractor.assert_any_call("met")
        mock_get_extractor.assert_any_call("rma")

    @patch("etl.pipeline.extract.extract.get_extractor")
    def test_run_extract_handles_extractor_failure(self, mock_get_extractor):
        """Test that extraction continues even if one extractor fails."""
        from etl.pipeline.extract.extract import run_extract

        # Create mock extractors - one that fails, one that succeeds
        failing_extractor = Mock(side_effect=Exception("API Error"))
        success_extractor = Mock()

        def extractor_side_effect(slug):
            if slug == "met":
                return failing_extractor
            return success_extractor

        mock_get_extractor.side_effect = extractor_side_effect

        # Run extraction - should not raise exception
        run_extract(["met", "smk"])

        # Verify both extractors were called despite one failing
        failing_extractor.assert_called_once()
        success_extractor.assert_called_once()
