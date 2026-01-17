"""
Unit tests for translation service.

Tests the translation service's ability to:
- Pass through English queries without translation
- Translate Danish/Dutch queries to English
- Gracefully degrade on timeout or connection errors
- Handle unsupported languages

Following CLAUDE.md test principles:
- What-focused: Test business outcomes (translation results)
- Mock expensive dependencies: Mock DeepL API calls
- Keep tests simple and focused
"""

import pytest
from unittest.mock import patch, MagicMock

import deepl

from artsearch.src.services.translation_service import (
    translate_to_english,
    TranslationResult,
    SUPPORTED_LANGUAGES,
)


@pytest.mark.unit
class TestTranslationService:
    """Unit tests for translation service."""

    def test_english_passthrough_no_translation(self):
        """English queries should pass through without translation."""
        result = translate_to_english("sunset", "en")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "sunset"
        assert result.original_text == "sunset"
        assert result.source_language == "en"
        assert result.translation_used is False

    @patch("artsearch.src.services.translation_service._get_translator")
    def test_danish_translation_success(self, mock_get_translator):
        """Danish queries should be translated to English."""
        # Mock successful DeepL response
        mock_translator = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "sunset"
        mock_translator.translate_text.return_value = mock_result
        mock_get_translator.return_value = mock_translator

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "sunset"
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is True

        # Verify DeepL API was called correctly
        mock_translator.translate_text.assert_called_once_with(
            "solnedgang",
            source_lang="DA",
            target_lang="EN-US",
        )

    @patch("artsearch.src.services.translation_service._get_translator")
    def test_dutch_translation_success(self, mock_get_translator):
        """Dutch queries should be translated to English."""
        # Mock successful DeepL response
        mock_translator = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "forest"
        mock_translator.translate_text.return_value = mock_result
        mock_get_translator.return_value = mock_translator

        result = translate_to_english("bos", "nl")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "forest"
        assert result.original_text == "bos"
        assert result.source_language == "nl"
        assert result.translation_used is True

        # Verify DeepL API was called correctly
        mock_translator.translate_text.assert_called_once_with(
            "bos",
            source_lang="NL",
            target_lang="EN-US",
        )

    @patch("artsearch.src.services.translation_service._get_translator")
    def test_connection_error_graceful_degradation(self, mock_get_translator):
        """On connection error, should return original query without failing."""
        # Mock connection error
        mock_translator = MagicMock()
        mock_translator.translate_text.side_effect = deepl.DeepLException("Connection failed")
        mock_get_translator.return_value = mock_translator

        result = translate_to_english("bos", "nl")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "bos"  # Original query
        assert result.original_text == "bos"
        assert result.source_language == "nl"
        assert result.translation_used is False

    @patch("artsearch.src.services.translation_service._get_translator")
    def test_authorization_error_graceful_degradation(self, mock_get_translator):
        """On authorization error, should return original query without failing."""
        # Mock authorization error
        mock_translator = MagicMock()
        mock_translator.translate_text.side_effect = deepl.AuthorizationException("Invalid API key")
        mock_get_translator.return_value = mock_translator

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "solnedgang"  # Original query
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is False

    @patch("artsearch.src.services.translation_service._get_translator")
    def test_quota_exceeded_graceful_degradation(self, mock_get_translator):
        """On quota exceeded error, should return original query without failing."""
        # Mock quota exceeded error
        mock_translator = MagicMock()
        mock_translator.translate_text.side_effect = deepl.QuotaExceededException("Quota exceeded")
        mock_get_translator.return_value = mock_translator

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "solnedgang"  # Original query
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is False

    def test_unsupported_language_defaults_to_english(self):
        """Unsupported language codes should default to English (passthrough)."""
        result = translate_to_english("test query", "xx")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "test query"
        assert result.original_text == "test query"
        assert result.source_language == "en"  # Defaulted to English
        assert result.translation_used is False

    def test_supported_languages_constant(self):
        """Verify SUPPORTED_LANGUAGES constant has expected values."""
        assert SUPPORTED_LANGUAGES == ["en", "da", "nl"]

    @patch("artsearch.src.services.translation_service.config")
    def test_translation_disabled_returns_original(self, mock_config):
        """When translation is disabled, should return original query."""
        mock_config.translation_enabled = False

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "solnedgang"
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is False
