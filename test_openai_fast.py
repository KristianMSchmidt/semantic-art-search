#!/usr/bin/env python
"""
Test script for generating short artwork labels using OpenAI GPT-4o-mini.
Uses metadata only (no image) for fast and cheap label generation.

Output: One paragraph with objective facts suitable for artwork cards.
Format: Title (English), Medium, Year, Culture (if present).

Usage:
    docker compose -f docker-compose.dev.yml exec web python test_openai_fast.py
"""

import os
import sys
import requests
import django
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import time

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoconfig.settings")
django.setup()

from artsearch.src.services.museum_clients.utils import get_museum_api_url


# Hardcoded test data - change these to test different artworks
MUSEUM_SLUG = "smk"
OBJECT_NUMBER = "KMS1"
MUSEUM_DB_ID = "dummy_id"  # SMK doesn't use this, but required for API


SYSTEM_PROMPT = (
    "You are an art cataloger. Generate concise, factual labels for artwork cards. "
    "Use only the metadata provided. Write in clear, neutral English. "
    "Focus on objective facts: title, medium, year, and culture if present."
)


def get_user_prompt(metadata: str) -> str:
    """Generate user prompt for short label generation."""
    return (
        "Task: Write ONE single short paragraph (2-4 sentences) as a brief artwork label.\n"
        "\n"
        "Include:\n"
        "  • Title in English (provide translation if title is not in English)\n"
        "  • Medium (e.g., 'oil on canvas', 'bronze sculpture', 'watercolor')\n"
        "  • Year or date of creation\n"
        "  • Culture or origin if explicitly mentioned in metadata (e.g., 'Flemish Baroque', 'Ming Dynasty')\n"
        "\n"
        "Rules:\n"
        "  • Use ONLY information found in the metadata below\n"
        "  • Keep it factual and objective - no interpretation or speculation\n"
        "  • Do NOT include artist name (already shown separately)\n"
        "  • Do NOT include accession numbers, dimensions, credit lines, or copyright info\n"
        "  • If information is missing, omit it (don't guess)\n"
        "  • IMPORTANT: Output must be ONE SINGLE paragraph of continuous prose - NO lists, NO bullet points, NO line breaks\n"
        "\n"
        f"Here is the metadata for the artwork:\n{metadata}"
    )


def test_openai_fast():
    """Test OpenAI API with fast label generation (metadata only, no image)."""

    # Track total time
    total_start_time = time.time()

    print("=" * 80)
    print("OpenAI Fast Label Generation Test - GPT-4o-mini (Text Only)")
    print("=" * 80)

    # Load environment
    env_files = [".env.dev", ".env.prod"]
    for env_file in env_files:
        if Path(env_file).exists():
            load_dotenv(env_file)
            break

    # Load API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n❌ ERROR: OPENAI_API_KEY not found in environment!")
        print("Please add OPENAI_API_KEY to your .env.dev file")
        return False

    print(f"\n✓ API key found: {api_key[:8]}...{api_key[-4:]}")

    # Fetch metadata from museum API
    print("\n" + "-" * 80)
    print(f"Fetching artwork metadata from {MUSEUM_SLUG.upper()} API...")
    print("-" * 80)
    print(f"Museum: {MUSEUM_SLUG}")
    print(f"Object Number: {OBJECT_NUMBER}")

    api_url = get_museum_api_url(MUSEUM_SLUG, OBJECT_NUMBER, MUSEUM_DB_ID)

    if not api_url:
        print(f"❌ Could not get API URL for {MUSEUM_SLUG}")
        return False

    print(f"Fetching from: {api_url}")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()

        # Handle both JSON and XML responses (for RMA)
        content_type = response.headers.get("Content-Type", "")
        if "xml" in content_type.lower() or MUSEUM_SLUG == "rma":
            metadata_str = response.text
            print(f"\n✓ Metadata fetched successfully (XML)")
        else:
            metadata = response.json()
            metadata_str = str(metadata)
            print(f"\n✓ Metadata fetched successfully (JSON)")

    except Exception as e:
        print(f"❌ Failed to fetch metadata: {e}")
        return False

    # Test OpenAI API (text-only, no image)
    print("\n" + "-" * 80)
    print("Testing OpenAI API with GPT-4o-mini (metadata only)...")
    print("-" * 80)

    try:
        start_time = time.time()
        client = OpenAI(api_key=api_key)
        print(f"✓ OpenAI client initialized in {time.time() - start_time:.2f} seconds.")

        print(f"\nSending request to OpenAI (this should be fast)...")
        print(f"Metadata preview (first 500 chars): {metadata_str[:500]}...")

        # Always use gpt-4o-mini for fast, cheap label generation
        model = "gpt-4o-mini"
        print(f"Using model: {model}")

        start_time = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": get_user_prompt(metadata_str),
                },
            ],
            max_tokens=200,  # Short labels only need ~100-150 tokens
        )
        print(f"OpenAI request completed in {time.time() - start_time:.2f} seconds.")

        # Extract response
        label = response.choices[0].message.content

        print("\n" + "=" * 80)
        print("\n📝 Generated Label:\n")
        print(label)

        print("\n\n📊 API Usage:")
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        print(f"  Prompt tokens:     {prompt_tokens}")
        print(f"  Completion tokens: {completion_tokens}")
        print(f"  Total tokens:      {total_tokens}")
        print(f"  Model:             {response.model}")

        # Cost estimation for gpt-4o-mini
        # Prices per 1M tokens in USD: $0.15 input / $0.60 output
        input_rate = 0.15
        output_rate = 0.60

        input_cost = (prompt_tokens / 1_000_000) * input_rate
        output_cost = (completion_tokens / 1_000_000) * output_rate
        total_cost_usd = input_cost + output_cost

        print("\n💰 Estimated cost:")
        print(f"  Input:  ${input_cost:.6f} (at ${input_rate} / 1M)")
        print(f"  Output: ${output_cost:.6f} (at ${output_rate} / 1M)")
        print(f"  Total:  ${total_cost_usd:.6f}")

        # Print total time
        total_time = time.time() - total_start_time
        print(f"\n⏱️  Total time: {total_time:.2f} seconds")

        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: OpenAI API call failed!")
        print(f"Error: {e}")

        error_str = str(e).lower()
        if "invalid_api_key" in error_str or "incorrect api key" in error_str:
            print("\n💡 The API key appears to be invalid.")
            print("   Check your OPENAI_API_KEY in .env.dev")
        elif "insufficient_quota" in error_str or "quota" in error_str:
            print("\n💡 Your API key has insufficient quota (credits).")
            print("   Add credits at: https://platform.openai.com/account/billing")
        elif "rate_limit" in error_str:
            print("\n💡 Rate limit exceeded. Wait a moment and try again.")
        else:
            print("\n💡 Check the error message above for details.")

        return False


if __name__ == "__main__":
    print(f"\nTesting with: {OBJECT_NUMBER} ({MUSEUM_SLUG.upper()})")
    print("(Edit MUSEUM_SLUG, OBJECT_NUMBER, MUSEUM_DB_ID in script to test other artworks)")
    success = test_openai_fast()
    sys.exit(0 if success else 1)
