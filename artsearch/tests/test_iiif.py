"""
Unit tests for IIIF URL helpers.

Sample image URLs are real values from the prod TransformedData table.
"""

import pytest

from artsearch.src.utils.iiif import (
    get_iiif_info_url,
    get_iiif_service_url,
    get_iiif_sized_image_url,
)
from etl.pipeline.transform.transformers.aic_transformer import AicTransformer
from etl.pipeline.transform.transformers.cma_transformer import CmaTransformer
from etl.pipeline.transform.transformers.met_transformer import MetTransformer
from etl.pipeline.transform.transformers.nga_transformer import NgaTransformer
from etl.pipeline.transform.transformers.rma_transformer import RmaTransformer
from etl.pipeline.transform.transformers.smk_transformer import SmkTransformer


@pytest.mark.unit
@pytest.mark.parametrize(
    "museum_slug, image_url, expected",
    [
        (
            "smk",
            "https://iip.smk.dk/iiif/jp2/jq085p37r_KMS709.tif.reconstructed.tif.jp2",
            "https://iip.smk.dk/iiif/jp2/jq085p37r_KMS709.tif.reconstructed.tif.jp2",
        ),
        (
            "nga",
            "https://api.nga.gov/iiif/79811d62-ab1d-413b-a1ac-7a85cda57a57/full/full/0/default.jpg",
            "https://api.nga.gov/iiif/79811d62-ab1d-413b-a1ac-7a85cda57a57",
        ),
        (
            "rma",
            "https://iiif.micr.io/BmeAd/full/max/0/default.jpg",
            "https://iiif.micr.io/BmeAd",
        ),
    ],
)
def test_get_iiif_service_url(museum_slug, image_url, expected):
    assert get_iiif_service_url(museum_slug, image_url) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "museum_slug, image_url",
    [
        # Museums without (usable) IIIF; AIC's is behind a Cloudflare challenge
        ("aic", "https://www.artic.edu/iiif/2/65627d47-c7e1-b0e6-fcc1-8519602dc322/full/full/0/default.jpg"),
        ("cma", "https://openaccess-cdn.clevelandart.org/1985.291/1985.291_print.jpg"),
        ("met", "https://images.metmuseum.org/CRDImages/dp/original/DP886922.jpg"),
        # No image URL (e.g. SMK artworks without an IIIF image)
        ("smk", None),
        ("smk", ""),
        # Unexpected formats
        ("smk", "https://api.smk.dk/api/v1/thumbnail/3d8ddd91-d3d0.jpg"),
        ("nga", "https://api.nga.gov/iiif/79811d62/full/!800,800/0/default.jpg"),
        ("rma", "https://iiif.micr.io/BmeAd/full/800,/0/default.jpg"),
        # Another museum's URL format
        ("nga", "https://iiif.micr.io/BmeAd/full/max/0/default.jpg"),
        ("unknown", "https://iiif.micr.io/BmeAd/full/max/0/default.jpg"),
    ],
)
def test_get_iiif_service_url_returns_none(museum_slug, image_url):
    assert get_iiif_service_url(museum_slug, image_url) is None


@pytest.mark.unit
def test_get_iiif_info_url():
    assert (
        get_iiif_info_url("https://iiif.micr.io/BmeAd")
        == "https://iiif.micr.io/BmeAd/info.json"
    )


@pytest.mark.unit
def test_get_iiif_sized_image_url():
    assert (
        get_iiif_sized_image_url("https://iiif.micr.io/BmeAd", 1600)
        == "https://iiif.micr.io/BmeAd/full/!1600,1600/0/default.jpg"
    )


# The helper relies on the image_url format produced by the ETL transformers.
# These tests fail if a transformer changes that format, which would otherwise
# silently disable deep zoom for that museum.


@pytest.mark.unit
@pytest.mark.parametrize(
    "transformer, raw_json, expected",
    [
        (
            SmkTransformer(),
            {"image_iiif_id": "https://iip.smk.dk/iiif/jp2/5m60qx228_kms9059.tif.jp2"},
            "https://iip.smk.dk/iiif/jp2/5m60qx228_kms9059.tif.jp2",
        ),
        (
            NgaTransformer(),
            {"image": {"iiifurl": "https://api.nga.gov/iiif/88b584ac-904a-41f6-ae3a-0bada5224a3e"}},
            "https://api.nga.gov/iiif/88b584ac-904a-41f6-ae3a-0bada5224a3e",
        ),
        (
            RmaTransformer(),
            {
                "metadata": {
                    "rdf:RDF": {
                        "ore:Aggregation": {
                            "edm:isShownBy": {
                                "@rdf:resource": "https://iiif.micr.io/oxWKy/full/max/0/default.jpg"
                            }
                        }
                    }
                }
            },
            "https://iiif.micr.io/oxWKy",
        ),
    ],
)
def test_transformer_image_url_has_iiif_format(transformer, raw_json, expected):
    image_url = transformer.extract_image_url(raw_json)
    assert get_iiif_service_url(transformer.museum_slug, image_url) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "transformer, raw_json",
    [
        (AicTransformer(), {"image_id": "9904fce2-938a-881c-ca5a-f0f17eaadb9c"}),
        (
            CmaTransformer(),
            {"images": {"print": {"url": "https://openaccess-cdn.clevelandart.org/1923.544/1923.544_print.jpg"}}},
        ),
        (
            MetTransformer(),
            {"primaryImage": "https://images.metmuseum.org/CRDImages/dp/original/DP808091.jpg"},
        ),
    ],
)
def test_transformer_image_url_without_iiif(transformer, raw_json):
    image_url = transformer.extract_image_url(raw_json)
    assert image_url
    assert get_iiif_service_url(transformer.museum_slug, image_url) is None
