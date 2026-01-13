"""
Translation service for multilingual search support using LibreTranslate.

Provides text translation from supported languages to English for search queries.
Implements graceful degradation - if translation fails, returns original query.
"""

import logging
from dataclasses import dataclass
import requests
from requests.exceptions import Timeout, RequestException

from artsearch.src.config import config

logger = logging.getLogger(__name__)

# Supported source languages for translation
SUPPORTED_LANGUAGES = ["en", "da", "nl"]


@dataclass
class TranslationResult:
    """Result of a translation operation.

    Attributes:
        translated_text: The translated text (or original if translation failed/skipped)
        original_text: The original input text
        source_language: The source language code
        translation_used: Whether translation was actually performed
    """
    translated_text: str
    original_text: str
    source_language: str
    translation_used: bool


def translate_to_english(query: str, source_language: str) -> TranslationResult:
    """Translate a query from the source language to English.

    Args:
        query: The text query to translate
        source_language: ISO 639-1 language code (e.g., "da", "nl", "en")

    Returns:
        TranslationResult with translated text or original text if translation failed

    Notes:
        - If translation is disabled or source is English, returns original query
        - If translation fails (timeout, connection error), returns original query
        - Timeout is configurable via config.translation_timeout (default 2.0s)
        - Graceful degradation ensures search always works even if translation fails
    """
    # Validate language
    if source_language not in SUPPORTED_LANGUAGES:
        logger.warning(
            f"Unsupported language '{source_language}', defaulting to English"
        )
        source_language = "en"

    # Skip translation if disabled or already English
    if not config.translation_enabled or source_language == "en":
        return TranslationResult(
            translated_text=query,
            original_text=query,
            source_language=source_language,
            translation_used=False,
        )

    # Attempt translation with graceful degradation
    try:
        response = requests.post(
            f"{config.libretranslate_url}/translate",
            json={
                "q": query,
                "source": source_language,
                "target": "en",
                "format": "text",
            },
            timeout=config.translation_timeout,
        )
        response.raise_for_status()

        translated_text = response.json()["translatedText"]

        logger.info(
            f"[TRANSLATION] '{query}' ({source_language}) -> '{translated_text}' (en)"
        )

        return TranslationResult(
            translated_text=translated_text,
            original_text=query,
            source_language=source_language,
            translation_used=True,
        )

    except Timeout:
        logger.warning(
            f"Translation timeout after {config.translation_timeout}s, "
            f"using original query: '{query}'"
        )
        return TranslationResult(
            translated_text=query,
            original_text=query,
            source_language=source_language,
            translation_used=False,
        )

    except RequestException as e:
        logger.warning(
            f"Translation request failed ({e.__class__.__name__}), "
            f"using original query: '{query}'"
        )
        return TranslationResult(
            translated_text=query,
            original_text=query,
            source_language=source_language,
            translation_used=False,
        )
