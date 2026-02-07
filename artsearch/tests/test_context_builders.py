"""
Unit tests for context builder helper functions.

These are pure functions that don't need Django DB or external services.
"""

import json

import pytest

from artsearch.views.context_builders import prepare_initial_label, prepare_items_json


class TestPrepareItemsJson:
    def test_basic_items_without_short_label(self):
        items = [
            {"value": "painting", "label": "paintings", "count": 10},
            {"value": "drawing", "label": "drawings", "count": 5},
        ]
        result = json.loads(prepare_items_json(items))
        assert result == [
            {"value": "painting", "label": "paintings"},
            {"value": "drawing", "label": "drawings"},
        ]

    def test_items_with_short_label(self):
        items = [
            {"value": "met", "label": "Metropolitan Museum of Art", "short_label": "The Met"},
            {"value": "smk", "label": "Statens Museum for Kunst", "short_label": "SMK"},
        ]
        result = json.loads(prepare_items_json(items))
        assert result == [
            {"value": "met", "label": "Metropolitan Museum of Art", "short_label": "The Met"},
            {"value": "smk", "label": "Statens Museum for Kunst", "short_label": "SMK"},
        ]

    def test_mixed_items_with_and_without_short_label(self):
        items = [
            {"value": "painting", "label": "paintings"},
            {"value": "met", "label": "Metropolitan Museum of Art", "short_label": "The Met"},
        ]
        result = json.loads(prepare_items_json(items))
        assert result == [
            {"value": "painting", "label": "paintings"},
            {"value": "met", "label": "Metropolitan Museum of Art", "short_label": "The Met"},
        ]


class TestPrepareInitialLabel:
    ALL_MUSEUMS = ["smk", "cma", "rma", "met"]
    MUSEUM_ITEMS = [
        {"value": "smk", "label": "Statens Museum for Kunst", "short_label": "SMK"},
        {"value": "cma", "label": "Cleveland Museum of Art", "short_label": "Cleveland"},
        {"value": "rma", "label": "Rijksmuseum", "short_label": "Rijksmuseum"},
        {"value": "met", "label": "Metropolitan Museum of Art", "short_label": "The Met"},
    ]

    ALL_WORK_TYPES = ["painting", "drawing", "print"]
    WORK_TYPE_ITEMS = [
        {"value": "painting", "label": "paintings"},
        {"value": "drawing", "label": "drawings"},
        {"value": "print", "label": "prints"},
    ]

    def test_returns_tuple(self):
        result = prepare_initial_label([], self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_all_selected_returns_all_label(self):
        label, short = prepare_initial_label(
            self.ALL_MUSEUMS, self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS
        )
        assert label == "All Museums"
        assert short == "All Museums"

    def test_none_selected_returns_all_label(self):
        label, short = prepare_initial_label(
            [], self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS
        )
        assert label == "All Museums"
        assert short == "All Museums"

    def test_single_museum_returns_full_and_short_labels(self):
        label, short = prepare_initial_label(
            ["met"], self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS
        )
        # .capitalize() lowercases all but the first character
        assert label == "Metropolitan museum of art"
        assert short == "The met"

    def test_single_museum_same_short_label(self):
        label, short = prepare_initial_label(
            ["rma"], self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS
        )
        assert label == "Rijksmuseum"
        assert short == "Rijksmuseum"

    def test_single_work_type_no_short_label(self):
        label, short = prepare_initial_label(
            ["painting"], self.ALL_WORK_TYPES, "work_types", self.WORK_TYPE_ITEMS
        )
        assert label == "Paintings"
        assert short == "Paintings"

    def test_multiple_selected_returns_count(self):
        label, short = prepare_initial_label(
            ["smk", "met"], self.ALL_MUSEUMS, "museums", self.MUSEUM_ITEMS
        )
        assert label == "2 Museums"
        assert short == "2 Museums"

    def test_multiple_work_types_returns_count(self):
        label, short = prepare_initial_label(
            ["painting", "drawing"], self.ALL_WORK_TYPES, "work_types", self.WORK_TYPE_ITEMS
        )
        assert label == "2 Work Types"
        assert short == "2 Work Types"

    def test_single_item_without_dropdown_items_fallback(self):
        label, short = prepare_initial_label(
            ["smk"], self.ALL_MUSEUMS, "museums", None
        )
        assert label == "1 Museum"
        assert short == "1 Museum"
