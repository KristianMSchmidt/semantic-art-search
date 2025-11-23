#!/usr/bin/env python
"""
Test script to verify OpenAI API key works with GPT-4o vision capabilities.
Fetches artwork metadata from museum API and image from S3 bucket.

Usage:
    docker compose -f docker-compose.dev.yml exec web python test_openai_key.py [object_number] [museum_slug]

Examples:
    docker compose -f docker-compose.dev.yml exec web python test_openai_key.py KMS1 smk
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
from etl.services.bucket_service import get_bucket_image_url


system_prompt_old = (
    "You are an art historian. Provide factual, grounded descriptions of artworks "
    "based solely on their metadata. Write in clear, neutral prose suitable for a museum label. "
    "Do not speculate or interpret beyond what the metadata explicitly supports."
)


def user_prompt_old(metadata: str) -> str:
    return (
        "Task: Write a single concise paragraph (7-10 sentences) as a museum wall label.\n"
        "Tone: clear, neutral, and informative.\n"
        "Rules:\n"
        "  • Use ONLY information found in the metadata below.\n"
        "  • Do NOT include credit lines, accession numbers.\n"
        "  • Do NOT include the dimensions of the artwork. \n"
        "  • Do NOT include the informatino about license or copyright.\n"
        "  • Do NOT include info about if the artwork is currently on display or in storage.\n"
        "  • If the metadata does not include descriptions of the artwork itself, don't guess, focus on the artist instead (or other relevant things from the metadata).\n"
        "  • If the subject is a well-known biblical, mythological, or historical scene, name it and briefly explain its context.\n"  # also if not in metadata?
        "  • Avoid jargon, florid language, or speculation about the artist’s intent.\n"
        "  • If there is is only mimimal relevant metadata, feel free to writa a very short label.\n"
        "  • Remember: Your output should be one coherent paragraph of prose (no lists or bullit points).\n\n"
        f"Here is the metadata for the artwork:\n{metadata}"
    )


system_prompt = (
    "You are an art historian. Provide factual, grounded presentations of artworks "
    "using both the metadata and the image. Write in clear, neutral prose suitable for a museum wall label. "
    "Prioritize metadata where it provides relevant facts, but you may also rely on what is clearly visible in the image "
    "to describe the subject, composition, and visual characteristics. "
    "Never contradict the metadata, and never speculate beyond what is explicitly stated or directly observable."
)


def user_prompt(metadata: str) -> str:
    return (
        "Task: Write one coherent paragraph (7–10 sentences) for a museum wall label.\n"
        "\n"
        "Use both the provided metadata and the image thumbnail to inform your description.\n"
        "Priorities:\n"
        "  1) Describe the artwork itself: what it is, who made it, its title and medium, "
        "     and what it depicts (figures, objects, actions, setting), drawing on both metadata and the image.\n"
        "  2) Add concise and relevant information about the artist only if present in the metadata, "
        "     especially when it helps understand this specific artwork.\n"
        "  3) Mention what makes the artwork interesting or significant when this is supported by the metadata "
        "     (such as its context, commission, series, subject, or reception). If such information is absent, omit it.\n"
        "\n"
        "Rules:\n"
        "  • Don't spend time telling what we can all see in the image. Focus on context that enriches understanding.\n"
        "   • It title is not in English, provide an English translation in parentheses if possible.\n"
        "    • Do NOT contradict the metadata. If metadata and image appear inconsistent, follow the metadata.\n"
        "  • Do NOT include credit lines, accession numbers, inventory IDs, dimensions, license/copyright info, "
        "    or whether the work is on display or in storage.\n"
        "  • If the metadata lacks a description of the motif or subject, use the image to give a straightforward, factual "
        "    description of what is depicted instead of guessing about meaning.\n"
        "  • If the subject is a well-known biblical, mythological, or historical scene, you may identify and briefly explain it "
        "    when this is clearly indicated by the metadata OR unmistakably recognizable from the image "
        "    (e.g. the Annunciation, the Crucifixion, Venus and Mars).\n"
        "  • Avoid jargon, florid language, and speculation about the artist’s psychology, intentions, or hidden symbolism.\n"
        "  • If there is very little relevant metadata, write a short, factual paragraph rather than padding with vague statements.\n"
        "  • The output must be a single paragraph of continuous prose, without headings, labels, lists, or bullet points.\n\n"
        f"Here is the metadata for the artwork:\n{metadata}"
    )


def test_openai_key(object_number: str = "KMS1", museum_slug: str = "smk"):
    """Test OpenAI API key with artwork from museum API."""

    print("=" * 80)
    print("OpenAI API Key Test - GPT-4o Vision")
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

    print("\n✓ API key found in environment.")

    # Fetch metadata from museum API
    print("\n" + "-" * 80)
    print(f"Fetching artwork metadata from {museum_slug.upper()} API...")
    print("-" * 80)
    print(f"Object Number: {object_number}")

    # Get API URL (use dummy museum_db_id for now - only SMK supported)
    museum_db_id = "dummy_id"  # SMK doesn't use this
    api_url = get_museum_api_url(museum_slug, object_number, museum_db_id)

    if not api_url:
        print(f"❌ Could not get API URL for {museum_slug}")
        return False

    print(f"Fetching from: {api_url}")

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        metadata = response.json()
        print(f"\n✓ Metadata fetched successfully (raw JSON)")
    except Exception as e:
        print(f"❌ Failed to fetch metadata: {e}")
        return False

    # Get S3 image URL using bucket service
    image_url = get_bucket_image_url(
        museum=museum_slug,
        object_number=object_number,
        use_etl_bucket=False,  # Use app/production bucket
    )

    print(f"  Image URL: {image_url}")

    # Test OpenAI API
    print("\n" + "-" * 80)
    print("Testing OpenAI API with GPT-4o...")
    print("-" * 80)

    try:
        start_time = time.time()
        client = OpenAI(api_key=api_key)
        print(f"✓ OpenAI client initialized in {time.time() - start_time:.2f} seconds.")

        # Send ALL metadata as JSON string
        metadata_str = str(metadata)

        print(f"\nSending request to OpenAI (this may take 5-10 seconds)...")
        print(f"Metadata preview (first 500 chars): {metadata_str[:500]}...")

        # Call GPT-4o-mini with vision (faster and cheaper than GPT-4o)
        start_time = time.time()
        model = "gpt-4o" if len(metadata_str) > 4000 else "gpt-4o-mini"
        print(f"Using model: {model}")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt(metadata_str)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "low",  # Use low detail for faster/cheaper analysis
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,  # Reduced from 1000 (only need 2-3 sentences)
        )
        print(f"OPEN API Request completed in {time.time() - start_time:.2f} seconds.")
        # Extract response
        description = response.choices[0].message.content

        print("\n" + "=" * 80)

        print("\n📝 Generated Description:\n")
        print(description)

        print("\n\n📊 API Usage:")
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        print(f"  Prompt tokens:     {prompt_tokens}")
        print(f"  Completion tokens: {completion_tokens}")
        print(f"  Total tokens:      {total_tokens}")
        print(f"  Model:             {response.model}")

        # --- Cost estimation (update rates if OpenAI pricing changes) ---
        # Prices per 1M tokens in USD (Chat Completions), as of current docs:
        # gpt-4o-mini: $0.15 input / $0.60 output per 1M tokens
        # gpt-4o:      $5.00 input / $15.00 output per 1M tokens
        pricing = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 5.00, "output": 15.00},
        }

        # Use the actual model string returned (e.g. "gpt-4o-mini", "gpt-4o-2024-05-13")
        model_key = response.model
        # Fallback: if it's a dated/suffixed variant, match on prefix
        if model_key not in pricing:
            for name in pricing:
                if model_key.startswith(name):
                    model_key = name
                    break

        print("\n💰 Estimated cost:")
        if model_key in pricing:
            rates = pricing[model_key]
            input_cost = (prompt_tokens / 1_000_000) * rates["input"]
            output_cost = (completion_tokens / 1_000_000) * rates["output"]
            total_cost_usd = input_cost + output_cost

            print(f"  Input:  ${input_cost:.6f} (at ${rates['input']} / 1M)")
            print(f"  Output: ${output_cost:.6f} (at ${rates['output']} / 1M)")
            print(f"  Total:  ${total_cost_usd:.6f}")
        else:
            print("  (No pricing table for this model key; please update the script.)")

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
        elif "could not download image" in error_str or "failed to fetch" in error_str:
            print("\n💡 Failed to fetch image from S3 bucket.")
            print("   The image may not be uploaded yet.")
            print(f"   Expected URL: {image_url}")
        else:
            print("\n💡 Check the error message above for details.")

        return False


if __name__ == "__main__":
    object_number = sys.argv[1] if len(sys.argv) > 1 else "KMS1"
    museum_slug = sys.argv[2] if len(sys.argv) > 2 else "smk"
    print(f"\nTesting with: {object_number} ({museum_slug.upper()})")
    success = test_openai_key(object_number, museum_slug)
    sys.exit(0 if success else 1)
