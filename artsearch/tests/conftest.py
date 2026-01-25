"""
Pytest configuration for artsearch tests.
"""

import pytest


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    """Disable django-ratelimit for all tests to prevent test interference."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all registered caches before and after each test."""
    from artsearch.src.cache_registry import clear_all_caches

    clear_all_caches()
    yield
    clear_all_caches()
