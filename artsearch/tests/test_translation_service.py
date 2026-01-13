"""
Unit tests for translation service.

Tests the translation service's ability to:
- Pass through English queries without translation
- Translate Danish/Dutch queries to English
- Gracefully degrade on timeout or connection errors
- Handle unsupported languages

Following CLAUDE.md test principles:
- What-focused: Test business outcomes (translation results)
- Mock expensive dependencies: Mock HTTP requests to LibreTranslate
- Keep tests simple and focused
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, RequestException

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

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_danish_translation_success(self, mock_post):
        """Danish queries should be translated to English."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"translatedText": "sunset"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "sunset"
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is True

        # Verify API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "translate" in call_args[0][0]
        assert call_args[1]["json"]["q"] == "solnedgang"
        assert call_args[1]["json"]["source"] == "da"
        assert call_args[1]["json"]["target"] == "en"

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_dutch_translation_success(self, mock_post):
        """Dutch queries should be translated to English."""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"translatedText": "forest"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = translate_to_english("bos", "nl")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "forest"
        assert result.original_text == "bos"
        assert result.source_language == "nl"
        assert result.translation_used is True

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_timeout_graceful_degradation(self, mock_post):
        """On timeout, should return original query without failing."""
        # Mock timeout exception
        mock_post.side_effect = Timeout("Connection timeout")

        result = translate_to_english("solnedgang", "da")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "solnedgang"  # Original query
        assert result.original_text == "solnedgang"
        assert result.source_language == "da"
        assert result.translation_used is False

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_connection_error_graceful_degradation(self, mock_post):
        """On connection error, should return original query without failing."""
        # Mock connection error
        mock_post.side_effect = RequestException("Connection failed")

        result = translate_to_english("bos", "nl")

        assert isinstance(result, TranslationResult)
        assert result.translated_text == "bos"  # Original query
        assert result.original_text == "bos"
        assert result.source_language == "nl"
        assert result.translation_used is False

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_http_error_graceful_degradation(self, mock_post):
        """On HTTP error (4xx/5xx), should return original query without failing."""
        # Mock HTTP error via raise_for_status
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = RequestException("500 Server Error")
        mock_post.return_value = mock_response

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

    @patch("artsearch.src.services.translation_service.requests.post")
    def test_timeout_uses_config_timeout_value(self, mock_post):
        """Translation should use timeout value from config."""
        from artsearch.src.services.translation_service import config

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {"translatedText": "sunset"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        translate_to_english("solnedgang", "da")

        # Verify timeout parameter was passed
        call_args = mock_post.call_args
        assert call_args[1]["timeout"] == config.translation_timeout
