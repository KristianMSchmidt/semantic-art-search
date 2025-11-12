"""Service for generating AI-powered artwork descriptions using OpenAI GPT-4o vision."""

import requests
from openai import OpenAI

from artsearch.src.config import config
from artsearch.src.services.museum_clients.utils import get_museum_api_url
from etl.services.bucket_service import get_bucket_image_url


SYSTEM_PROMPT_OLD = (
    "You are an art historian. Provide factual, grounded presentations of artworks "
    "using both the metadata and the image. Write in clear, neutral prose suitable for a museum wall label. "
    "Prioritize metadata where it provides relevant facts, but you may also rely on what is clearly visible in the image "
    "to describe the subject, composition, and visual characteristics. "
    "Never contradict the metadata, and never speculate beyond what is explicitly stated or directly observable."
)


def get_user_prompt_old(metadata: str) -> str:
    """Generate user prompt with metadata for artwork description."""
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
        "  • Avoid jargon, florid language, and speculation about the artist's psychology, intentions, or hidden symbolism.\n"
        "  • If there is very little relevant metadata, write a short, factual paragraph rather than padding with vague statements.\n"
        "  • The output must be a single paragraph of continuous prose, without headings, labels, lists, or bullet points.\n\n"
        f"Here is the metadata for the artwork:\n{metadata}"
    )


SYSTEM_PROMPT_OLD2 = (
    "You are an art historian. Provide factual, grounded presentations of artworks "
    "using both the metadata and the image. Write in clear, neutral prose suitable for a museum wall label. "
    "Prioritize metadata where it provides relevant facts, but you may also rely on what is clearly visible in the image "
    "to describe the subject, composition, and visual characteristics. "
    "Never contradict the metadata, and never speculate beyond what is explicitly stated or directly observable."
)


SYSTEM_PROMPT = (
    "You are an art historian. Write concise, factual wall labels that help visitors "
    "understand artworks. Use both the metadata and the image as your sources. "
    "Treat the metadata as your main reference for factual details and for any "
    "documented context or interpretation it includes. The image may be used to "
    "describe clear subject matter, composition, and visual character. "
    "Your goal is to open up the artwork—explain what it shows, how it is made, "
    "and how it fits within its artistic or historical setting—without inventing "
    "unsupported facts. Keep the tone clear, neutral, and accessible."
)


def get_user_prompt(metadata: str) -> str:
    """Generate user prompt with metadata for artwork description."""
    return (
        "Task: Write one coherent paragraph (7–10 sentences) for a museum wall label.\n"
        "\n"
        "Use both the provided metadata and the image thumbnail to inform your description.\n"
        "Priorities:\n"
        "  1) Describe the artwork itself: what it is, its title (in English translation if applicable), medium, "
        "     and what it depicts (figures, objects, actions, setting), drawing on both metadata and the image. \n"
        "  2) Add concise and relevant information about the artist when it makes sense and is clearly related "
        "     to this specific artwork. Prioritize info from metadata. The artist’s name and year of production are already shown above the text, "
        "     so include them only if doing so improves the flow or adds meaningful context.\n"
        "  3) Mention what makes the artwork interesting or significant, when this is supported by the metadata "
        "     (such as its context, commission, series, subject, or reception). If such information is absent, omit it.\n"
        "\n"
        "Rules:\n"
        "  • Focus on context that enriches understanding rather than restating what is visually obvious.\n"
        "  • If the title is not in English, provide an English translation in parentheses. Use quotation marks for titles, "
        "    never italics or asterisks.\n"
        "  • Do NOT contradict the metadata. If metadata and image appear inconsistent, follow the metadata.\n"
        "  • Do NOT include credit lines, accession numbers, inventory IDs, dimensions, license/copyright info, "
        "    or whether the work is on display or in storage.\n"
        "  • If the metadata lacks a description of the motif or subject, use the image to provide a straightforward, factual "
        "    account of what is depicted rather than speculating about meaning.\n"
        "  • If the subject is a well-known biblical, mythological, or historical scene, you may identify and briefly explain it "
        "    when this is clearly indicated by the metadata OR unmistakably recognizable from the image "
        "    (e.g. the Annunciation, the Crucifixion, Venus and Mars).\n"
        "  • Avoid jargon, florid language, and speculation about the artist's psychology, intentions, or hidden symbolism.\n"
        "  • If there is very little relevant metadata, write a short, factual paragraph rather than padding with vague statements.\n"
        "  • The output must be a single paragraph of continuous prose, without headings, labels, lists, or bullet points.\n\n"
        f"Here is the metadata for the artwork:\n{metadata}"
    )


def generate_description(
    museum_slug: str, object_number: str, museum_db_id: str, force_regenerate: bool = False
) -> str:
    """
    Generate an AI-powered artwork description using OpenAI GPT-4o vision.
    Uses database caching to avoid redundant API calls.

    Args:
        museum_slug: Museum identifier (e.g., 'smk', 'met')
        object_number: Artwork object number
        museum_db_id: Museum's internal database ID
        force_regenerate: If True, bypass cache and generate fresh description

    Returns:
        Generated description string, or error message if generation fails
    """
    from artsearch.models import ArtworkDescription

    # Check cache first (unless force regenerate)
    if not force_regenerate:
        try:
            cached = ArtworkDescription.objects.get(
                museum_slug=museum_slug, object_number=object_number
            )
            print(f"Using cached description for {museum_slug}:{object_number}")
            return cached.description
        except ArtworkDescription.DoesNotExist:
            print(f"No cached description found for {museum_slug}:{object_number}, generating new one")
            pass
    else:
        print(f"Force regenerate requested for {museum_slug}:{object_number}")

    # Generate new description
    try:
        # Fetch metadata from museum API
        api_url = get_museum_api_url(museum_slug, object_number, museum_db_id)
        if not api_url:
            return "Error: Could not fetch artwork metadata (unsupported museum)."

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            # Handle both JSON and XML responses
            content_type = response.headers.get("Content-Type", "")
            if "xml" in content_type.lower() or museum_slug == "rma":
                # For XML responses (RMA), use raw text
                metadata_str = response.text
            else:
                # For JSON responses (SMK, MET, CMA), parse and convert to string
                metadata = response.json()
                metadata_str = str(metadata)
        except Exception as e:
            return f"Error: Failed to fetch artwork metadata from museum API: {str(e)}"

        # Get image URL from S3 bucket
        image_url = get_bucket_image_url(
            museum=museum_slug,
            object_number=object_number,
            use_etl_bucket=False,  # Use app/production bucket
        )

        # Initialize OpenAI client
        client = OpenAI(api_key=config.openai_api_key)

        # Select model based on metadata size (gpt-4o-mini is cheaper for small metadata)
        model = "gpt-4o" if len(metadata_str) > 4000 else "gpt-4o-mini"
        print(f"Using model: {model}")

        # Call OpenAI API with vision
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": get_user_prompt(metadata_str)},
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
            max_tokens=2000,
        )

        # Extract description
        description = response.choices[0].message.content
        if not description:
            return "Error: OpenAI returned empty description."

        # Save to cache (only if successful, not errors)
        if not description.startswith("Error:"):
            ArtworkDescription.objects.update_or_create(
                museum_slug=museum_slug,
                object_number=object_number,
                defaults={"description": description},
            )
            print(f"Saved description to cache for {museum_slug}:{object_number}")

        return description

    except Exception as e:
        error_str = str(e).lower()
        if "invalid_api_key" in error_str or "incorrect api key" in error_str:
            return "Error: Invalid OpenAI API key. Please check your configuration."
        elif "insufficient_quota" in error_str or "quota" in error_str:
            return (
                "Error: OpenAI API quota exceeded. Please add credits to your account."
            )
        elif "rate_limit" in error_str:
            return "Error: OpenAI rate limit exceeded. Please try again in a moment."
        elif "could not download image" in error_str or "failed to fetch" in error_str:
            return (
                "Error: Failed to load artwork image. The image may not be available."
            )
        else:
            return f"Error: Failed to generate description: {str(e)}"
