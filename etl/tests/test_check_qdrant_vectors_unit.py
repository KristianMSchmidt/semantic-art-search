"""
Unit tests for zero-vector detection in check_qdrant_vectors.
"""
import pytest
from etl.management.commands.check_qdrant_vectors import (
    count_zero_vectors,
    is_zero_vector,
)


@pytest.mark.unit
class TestZeroVectorDetection:
    def test_is_zero_vector(self):
        assert is_zero_vector([0.0, 0.0, 0.0])
        assert not is_zero_vector([0.0, 0.1, 0.0])
        assert not is_zero_vector([-0.2, 0.0])

    def test_count_zero_vectors_per_name(self):
        point_vectors = [
            {"image_jina": [0.0, 0.0], "image_clip": [0.3, 0.1]},
            {"image_jina": [0.0, 0.0], "image_clip": [0.0, 0.0]},
            {"image_jina": [0.5, 0.2], "image_clip": [0.1, 0.0]},
        ]

        assert count_zero_vectors(point_vectors) == {
            "image_jina": 2,
            "image_clip": 1,
        }

    def test_count_zero_vectors_empty(self):
        assert count_zero_vectors([]) == {}
