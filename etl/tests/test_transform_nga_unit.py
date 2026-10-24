"""
Unit tests for NGA production date extraction.

NGA fills beginyear/endyear with the artist's lifespan for undated works,
so these must not be stored as production dates.
"""

import pytest

from etl.pipeline.transform.transformers.nga_transformer import NgaTransformer


@pytest.mark.unit
@pytest.mark.parametrize(
    "displaydate, beginyear, endyear, expected",
    [
        ("1796-1797", "1796", "1797", (1796, 1797)),
        ("18th century", "1700", "1799", (1700, 1799)),
        # Undated works: beginyear/endyear is the artist's lifespan
        ("", "1837", "1911", (None, None)),
        ("n.d.", "1829", "1905", (None, None)),
        ("Date Unknown ", "1799", "1885", (None, None)),
    ],
)
def test_extract_production_dates(displaydate, beginyear, endyear, expected):
    raw_json = {"displaydate": displaydate, "beginyear": beginyear, "endyear": endyear}
    assert NgaTransformer().extract_production_dates(raw_json) == expected


@pytest.mark.unit
def test_extract_production_dates_without_displaydate_field():
    raw_json = {"beginyear": "1837", "endyear": "1911"}
    assert NgaTransformer().extract_production_dates(raw_json) == (None, None)


@pytest.mark.unit
@pytest.mark.parametrize(
    "displaydate, expected",
    [
        ("c. 1310", "c. 1310"),
        ("", None),
        ("n.d.", None),
        ("Date Unknown ", None),
    ],
)
def test_extract_period(displaydate, expected):
    assert NgaTransformer().extract_period({"displaydate": displaydate}) == expected
