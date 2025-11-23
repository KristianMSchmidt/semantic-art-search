"""OpenAI API client for artwork description generation."""

import logging
from openai import OpenAI
from artsearch.src.config import config

logger = logging.getLogger(__name__)

# System prompt defining the AI's role and behavior
SYSTEM_PROMPT = (
    "You are an art historian. Write concise, factual wall labels that help visitors "
    "understand artworks. Use both the metadata and the image as your sources. "
    "Treat the metadata as your primary authority for titles, dates, artists, places, "
    "and historical context. The image may only be used to describe what is plainly "
    "visible: subject matter, composition, colours, light, and overall visual character.\n\n"
    "Never invent or guess factual information such as titles, dates, locations, "
    "identities of people, or symbolic meanings that are not clearly supported by "
    "the metadata. If you are not certain, leave it out.\n\n"
    "Your goal is to open up the artwork—explain what it shows, how it is made, and "
    "how it sits within its artistic or historical setting—without speculation. "
    "Keep the tone clear, neutral, and accessible, like a good museum wall label, "
    "not like a review or marketing text."
)


def _get_user_prompt(metadata: str) -> str:
    return (
        "Task: Write one coherent paragraph for a museum wall label.\n"
        "\n"
        "Use both the provided metadata and the image thumbnail to inform your description.\n"
        "\n"
        "Priorities:\n"
        "  1) Describe the artwork itself: what kind of work it is, its title (in English "
        "     translation if applicable), its medium, and what it depicts (figures, "
        "     objects, actions, setting). Base factual information (titles, dates, medium, "
        "     artist, place) on the metadata, not on guesses from the image.\n"
        "  2) Add concise and relevant information about the artist only when it clearly "
        "     relates to this specific artwork and is supported by the metadata. The "
        "     artist's name and year of production are already shown above the text, so "
        "     repeat them only if it improves the flow.\n"
        "  3) Mention what makes the artwork interesting or significant only when this is "
        "     supported by the metadata (for example its historical context, commission, "
        "     series, function, subject tradition, or reception). If such information is "
        "     absent, simply omit this dimension instead of inventing it.\n"
        "\n"
        "Rules:\n"
        "  • Provide clear, concrete visual description of what can be seen in the image "
        "    (figures, objects, setting, composition). This is especially important when "
        "    metadata lacks a subject description.\n"
        "  • If the title is not in English, provide an English translation in parentheses. "
        "    Use quotation marks for titles, never italics or asterisks.\n"
        "  • Do NOT contradict the metadata. If metadata and image appear inconsistent, "
        "    follow the metadata and avoid speculating about the discrepancy.\n"
        "  • Don't mention what museum the artwork is from, since this is already shown.\n"
        "  • If the metadata lacks a description of the motif or subject, use the image "
        "    to provide a straightforward, factual account of what is depicted without "
        "    guessing at symbolic meaning, story, or emotional intention.\n"
        "  • If the subject is a well-known biblical, mythological, or historical scene, "
        "    you may identify and briefly explain it only when this is clearly indicated "
        "    in the metadata. Do not infer specific stories purely from the image.\n"
        "  • Do not speculate about the artist's psychology, intentions, or hidden symbolism.\n"
        "  • Avoid stock phrases and vague praise such as 'invites the viewer', 'evocative', "
        "    'offers a glimpse', 'captures the essence', or 'timeless'. Prefer concrete, "
        "    descriptive sentences.\n"
        "  • Avoid clichés and subjective filler such as 'serene', 'captures a moment', "
        "    'reveals an intimate look', 'dynamic movement and grace', 'beautiful', "
        "    'striking', 'richly layered', or similar poetic or emotional language. "
        "    Use neutral, concrete description instead.\n"
        "    • Keep the paragraph concise. Aim for 5–7 clear sentences (roughly 90–130 words). "
        "    Do not add unnecessary detail or repeat information already visible elsewhere "
        "    on the page.\n"
        "  • If there is very little relevant metadata, write a short factual paragraph "
        "    (3–5 sentences) instead of padding with generic statements. In that case, "
        "    rely mainly on a clear visual description grounded in what can be seen.\n"
        "  • The output must be a single paragraph of continuous prose, without headings, "
        "    labels, lists, or bullet points.\n\n"
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
