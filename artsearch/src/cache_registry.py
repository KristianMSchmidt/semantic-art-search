"""
Central registry for LRU caches that need clearing during tests or admin operations.

Usage:
    @register_cache
    @lru_cache(maxsize=32)
    def my_cached_function(...):
        ...
"""

from typing import Callable, Any

_clearable_caches: list[Callable[..., Any]] = []


def register_cache(func: Callable[..., Any]) -> Callable[..., Any]:
    """Register a cached function for centralized clearing. Apply AFTER @lru_cache."""
    if not hasattr(func, "cache_clear"):
        raise TypeError(f"{func.__name__} must be decorated with @lru_cache first")
    _clearable_caches.append(func)
    return func


def clear_all_caches() -> int:
    """Clear all registered caches. Returns count of caches cleared."""
    for cached_func in _clearable_caches:
        cached_func.cache_clear()
    return len(_clearable_caches)


def get_cache_info() -> dict[str, Any]:
    """Get cache statistics for all registered caches."""
    return {func.__name__: func.cache_info() for func in _clearable_caches}
