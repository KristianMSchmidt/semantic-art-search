"""OpenAI API client for artwork description generation."""

import logging
from openai import OpenAI
from artsearch.src.config import config

logger = logging.getLogger(__name__)

# System prompt defining the AI's role and behavior
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


def _get_user_prompt(metadata: str) -> str:
    """Generate user prompt with metadata for artwork description.

    Args:
        metadata: String representation of cleaned metadata

    Returns:
        Formatted user prompt
    """
    return (
        "Task: Write one coherent paragraph (5–10 sentences) for a museum wall label.\n"
        "\n"
        "Use both the provided metadata and the image thumbnail to inform your description.\n"
        "Priorities:\n"
        "  1) Describe the artwork itself: what it is, its title (in English translation if applicable), medium, "
        "     and what it depicts (figures, objects, actions, setting), drawing on both metadata and the image. \n"
        "  2) Add concise and relevant information about the artist when it makes sense and is clearly related "
        "     to this specific artwork. Prioritize info from metadata. The artist's name and year of production are already shown above the text, "
        "     so include them only if doing so improves the flow or adds meaningful context.\n"
        "  3) Mention what makes the artwork interesting or significant, when this is supported by the metadata "
        "     (such as its context, commission, series, subject, or reception). If such information is absent, omit it.\n"
        "\n"
        "Rules:\n"
        "  • Focus on context that enriches understanding rather than restating what is visually obvious.\n"
        "  • If the title is not in English, provide an English translation in parentheses. Use quotation marks for titles, "
        "    never italics or asterisks.\n"
        "  • Do NOT contradict the metadata. If metadata and image appear inconsistent, follow the metadata.\n"
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


def generate_with_openai(
    metadata_str: str,
    image_url: str,
    model: str = "gpt-4o-mini",
) -> str:
    """Generate artwork description using OpenAI GPT-4o vision.

    Args:
        metadata_str: String representation of cleaned metadata
        image_url: URL to artwork image
        model: OpenAI model to use (default: gpt-4o-mini)

    Returns:
        Generated description string

    Raises:
        Exception: If OpenAI API call fails
    """
    # Initialize OpenAI client
    client = OpenAI(api_key=config.openai_api_key)

    try:
        # Call OpenAI API with vision
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _get_user_prompt(metadata_str)},
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
            raise ValueError("OpenAI returned empty description")

        return description

    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        # Re-raise to be handled by caller
        raise
