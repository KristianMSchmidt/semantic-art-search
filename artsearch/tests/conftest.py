"""
Pytest configuration for artsearch tests.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable django-ratelimit for all tests to prevent test interference."""
    settings.RATELIMIT_ENABLE = False
