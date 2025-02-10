def get_valid_limit(limit: str | None, default: int = 10) -> int:
    """Safely converts a limit to an integer, ensuring it is between 5 and 1000."""
    if limit is None:
        return default
    try:
        return max(5, min(1000, int(limit)))  # Clamp between 5 and 50
    except (ValueError, TypeError):
        return default
