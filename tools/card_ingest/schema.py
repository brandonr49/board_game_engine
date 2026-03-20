"""Schema discovery — sample card images and propose a JSON schema."""

import json
import random
from pathlib import Path

from .llm_provider import LLMProvider, SUPPORTED_IMAGE_FORMATS


DESCRIBE_CARD_PROMPT = """\
You are analyzing a board game card image. Describe ALL visible information on this card in detail:
- Card name/title
- Any numbers (cost, value, strength, etc.) and what they represent
- Card type or category (if indicated)
- Any text or abilities described on the card
- Colors, icons, or symbols that carry game meaning
- Any other distinguishing attributes

Be thorough — list every distinct piece of game-relevant information you can see.
Format your response as a structured list of attributes."""

SYNTHESIZE_SCHEMA_PROMPT = """\
You are designing a JSON schema for board game cards. Below are descriptions of {count} \
sample cards from the same game. Based on these descriptions:

1. Identify distinct card TYPES if they exist (e.g., "troop" vs "tactics", "creature" vs "spell").
2. For each card type, define a flat JSON object schema with appropriate field names and types.
3. Use simple types: "string", "int", "float", "bool", "string[]" (for lists of strings).
4. Include a "card_type" field in every schema to distinguish types.
5. Every field should be present on every card of that type (no optional fields — use null/empty defaults if needed).

Card descriptions:
{descriptions}

Respond with ONLY a valid JSON object mapping card type names to their schemas. Example format:
{{
  "troop": {{
    "card_type": "string",
    "name": "string",
    "color": "string",
    "value": "int"
  }},
  "tactics": {{
    "card_type": "string",
    "name": "string",
    "subtype": "string",
    "effect": "string"
  }}
}}

If all cards share the same structure, use a single type (e.g., "card").
Respond with ONLY the JSON, no explanation."""


def discover_images(directory: str) -> list[Path]:
    """Find all supported image files in the given directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    images = sorted(
        p for p in dir_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_FORMATS
    )
    return images


def sample_cards(images: list[Path], sample_size: int = 5) -> list[Path]:
    """Select a random sample of card images for schema discovery."""
    n = min(sample_size, len(images))
    return random.sample(images, n)


def describe_cards(provider: LLMProvider, image_paths: list[Path]) -> list[str]:
    """Send each sampled card to the LLM and collect descriptions."""
    descriptions = []
    for i, path in enumerate(image_paths, 1):
        print(f"  Analyzing card {i}/{len(image_paths)}: {path.name}")
        desc = provider.analyze_image(str(path), DESCRIBE_CARD_PROMPT)
        descriptions.append(desc)
    return descriptions


def propose_schema(provider: LLMProvider, descriptions: list[str]) -> dict:
    """Synthesize individual card descriptions into a unified schema proposal."""
    prompt = SYNTHESIZE_SCHEMA_PROMPT.format(
        count=len(descriptions),
        descriptions="\n\n---\n\n".join(
            f"Card {i+1}:\n{desc}" for i, desc in enumerate(descriptions)
        ),
    )
    raw = provider.analyze_text(prompt)

    # Extract JSON from response (handle markdown code fences)
    text = raw.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` wrapper
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        schema = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON for schema proposal.\n"
            f"Parse error: {e}\n"
            f"Raw response:\n{raw}"
        )

    return schema


def format_schema_for_display(schema: dict) -> str:
    """Pretty-print a schema dict for terminal display."""
    return json.dumps(schema, indent=2)


def save_schema(schema: dict, output_path: str) -> Path:
    """Write the confirmed schema to a JSON file."""
    path = Path(output_path)
    path.write_text(json.dumps(schema, indent=2) + "\n")
    return path


def load_schema(schema_path: str) -> dict:
    """Load a previously saved schema from disk."""
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return json.loads(path.read_text())
