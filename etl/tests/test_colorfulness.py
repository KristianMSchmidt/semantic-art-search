"""Tests for colourfulness scoring (etl/services/colorfulness_service.py)."""

from io import BytesIO, StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from PIL import Image

from artsearch.models import ArtworkStats
from etl.services.colorfulness_service import compute_colorfulness


def _png(img: Image.Image) -> bytes:
    out = BytesIO()
    img.save(out, format="PNG")  # lossless, so flat colours stay flat
    return out.getvalue()


def _two_tone(left: tuple, right: tuple, mode: str = "RGB") -> bytes:
    img = Image.new(mode, (200, 100), left)
    img.paste(Image.new(mode, (100, 100), right), (100, 0))
    return _png(img)


@pytest.mark.unit
def test_greyscale_scores_zero():
    assert compute_colorfulness(_two_tone(0, 255, mode="L")) == pytest.approx(0)
    assert compute_colorfulness(
        _two_tone((20, 20, 20), (240, 240, 240))
    ) == pytest.approx(0)


@pytest.mark.unit
def test_uniform_tint_scores_zero():
    """Yellowed paper on its own isn't colourful."""
    assert compute_colorfulness(
        _two_tone((230, 210, 160), (230, 210, 160))
    ) == pytest.approx(0)


@pytest.mark.unit
def test_contrasting_colours_score_higher_than_ink_on_paper():
    ink_on_paper = compute_colorfulness(_two_tone((230, 210, 160), (60, 50, 40)))
    red_and_blue = compute_colorfulness(_two_tone((200, 30, 30), (30, 60, 200)))
    assert red_and_blue > ink_on_paper > 0


@pytest.mark.integration
@pytest.mark.django_db
def test_compute_colorfulness_command_scores_only_unscored_rows():
    """Failed downloads stay unscored; --force rescores everything."""
    ArtworkStats.objects.create(
        museum_slug="smk", object_number="A", searchable_work_types=["print"]
    )
    ArtworkStats.objects.create(
        museum_slug="smk", object_number="B", searchable_work_types=["print"]
    )
    ArtworkStats.objects.create(
        museum_slug="smk",
        object_number="DONE",
        searchable_work_types=["print"],
        colorfulness=7.0,
    )

    def fake_score(artworks, workers):
        return [None if obj == "B" else 30.0 for _, obj in artworks]

    with patch(
        "etl.management.commands.compute_colorfulness.score_artworks",
        side_effect=fake_score,
    ) as mock_score:
        call_command("compute_colorfulness", stdout=StringIO())

    (artworks,) = mock_score.call_args.args
    assert sorted(obj for _, obj in artworks) == ["A", "B"]
    scores = dict(ArtworkStats.objects.values_list("object_number", "colorfulness"))
    assert scores == {"A": 30.0, "B": None, "DONE": 7.0}

    with patch(
        "etl.management.commands.compute_colorfulness.score_artworks",
        side_effect=fake_score,
    ):
        call_command("compute_colorfulness", "--force", stdout=StringIO())

    scores = dict(ArtworkStats.objects.values_list("object_number", "colorfulness"))
    assert scores == {"A": 30.0, "B": None, "DONE": 30.0}
