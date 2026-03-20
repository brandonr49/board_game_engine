"""Batch card extraction — apply a confirmed schema to all card images."""

import json
from pathlib import Path

from .llm_provider import LLMProvider


EXTRACT_CARD_PROMPT = """\
You are extracting structured data from a board game card image.

Use this JSON schema to determine what fields to extract. The schema maps card type \
names to their field definitions:

{schema}

Instructions:
1. Determine which card type this card belongs to.
2. Extract ALL fields defined in that type's schema.
3. Use the exact field names from the schema.
4. For "int" fields, return integers. For "string" fields, return strings.
   For "bool" fields, return true/false. For "string[]" fields, return arrays of strings.
5. If a field value is not visible or not applicable, use null.

Respond with ONLY a valid JSON object for this single card. No explanation."""


def extract_single_card(
    provider: LLMProvider, image_path: Path, schema: dict
) -> dict:
    """Extract structured data from a single card image.

    Returns a dict with the card data, plus "_source_image" metadata.
    """
    prompt = EXTRACT_CARD_PROMPT.format(schema=json.dumps(schema, indent=2))
    raw = provider.analyze_image(str(image_path), prompt)

    # Parse JSON from response
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        card_data = json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "_error": f"JSON parse error: {e}",
            "_raw_response": raw,
            "_source_image": image_path.name,
        }

    card_data["_source_image"] = image_path.name
    return card_data


def extract_batch(
    provider: LLMProvider,
    image_paths: list[Path],
    schema: dict,
    review_after: int = 3,
) -> tuple[list[dict], list[dict]]:
    """Extract structured data from all card images.

    Args:
        provider: LLM provider to use.
        image_paths: List of card image paths.
        schema: Confirmed schema dict.
        review_after: Pause for review after this many cards (0 to skip).

    Returns:
        (cards, flagged) — successfully extracted cards and error/flagged cards.
    """
    cards = []
    flagged = []

    for i, path in enumerate(image_paths, 1):
        print(f"  [{i}/{len(image_paths)}] {path.name}", end=" ")

        card = extract_single_card(provider, path, schema)

        if "_error" in card:
            print(f"⚠ ERROR: {card['_error']}")
            flagged.append(card)
        else:
            # Show a summary of what was extracted
            card_type = card.get("card_type", "?")
            card_name = card.get("name", card.get("title", "?"))
            print(f"→ {card_name} ({card_type})")
            cards.append(card)

        # Review checkpoint
        if review_after > 0 and i == review_after and i < len(image_paths):
            print(f"\n  --- Review checkpoint ({review_after} cards processed) ---")
            print("  Recent extractions:")
            for c in cards[-review_after:]:
                print(f"    {json.dumps(c, indent=2)}")

            response = input(
                "\n  [C]ontinue all / [S]top and save what we have / [Q]uit? "
            ).strip().lower()
            if response == "s":
                print("  Stopping early — saving extracted cards.")
                break
            elif response == "q":
                print("  Quitting without saving.")
                return [], flagged
            print()  # blank line before continuing

    return cards, flagged


def save_cards(cards: list[dict], output_path: str) -> Path:
    """Write extracted cards to a JSON file."""
    path = Path(output_path)
    path.write_text(json.dumps(cards, indent=2) + "\n")
    return path
