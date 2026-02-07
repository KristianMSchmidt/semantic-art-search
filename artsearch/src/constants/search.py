MAX_QUERY_LENGTH = 500

# Default work type filter applied on first page load (before user makes a selection).
# Options:
#   - Single type: ["painting"]
#   - Multiple types: ["painting", "drawing"]
#   - All types: None (no filtering)
DEFAULT_WORK_TYPE_FILTER: list[str] | None = ["painting"]
