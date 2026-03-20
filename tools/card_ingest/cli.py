"""Interactive CLI for card ingestion — ties together schema discovery, extraction, and parser generation."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .llm_provider import get_provider
from .schema import (
    describe_cards,
    discover_images,
    format_schema_for_display,
    load_schema,
    propose_schema,
    sample_cards,
    save_schema,
)
from .extractor import extract_batch, save_cards
from .parser_gen import generate_parser


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_step(n: int, text: str) -> None:
    print(f"\n── Step {n}: {text} ──\n")


def prompt_input(message: str, default: str | None = None) -> str:
    if default:
        result = input(f"{message} [{default}]: ").strip()
        return result or default
    return input(f"{message}: ").strip()


def prompt_choice(message: str, options: str = "Y/n") -> str:
    return input(f"{message} [{options}]: ").strip().lower()


def edit_schema_in_editor(schema: dict) -> dict:
    """Open schema in $EDITOR for user to modify, return updated schema."""
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="card_schema_"
    ) as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
        tmp_path = f.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path) as f:
            edited = json.load(f)
        return edited
    except subprocess.CalledProcessError:
        print("  Editor exited with error — keeping original schema.")
        return schema
    except json.JSONDecodeError as e:
        print(f"  Edited file has invalid JSON: {e}")
        print("  Keeping original schema.")
        return schema
    finally:
        os.unlink(tmp_path)


def edit_schema_inline(schema: dict) -> dict:
    """Let user paste a new JSON schema directly."""
    print("  Paste your edited JSON schema below (end with an empty line):")
    lines = []
    while True:
        line = input()
        if line.strip() == "":
            break
        lines.append(line)

    try:
        return json.loads("\n".join(lines))
    except json.JSONDecodeError as e:
        print(f"  Invalid JSON: {e}")
        print("  Keeping original schema.")
        return schema


def run_schema_discovery(provider, images, sample_size: int = 5) -> dict:
    """Interactive schema discovery loop."""
    while True:
        sampled = sample_cards(images, sample_size)
        print(f"  Sampled {len(sampled)} cards:")
        for p in sampled:
            print(f"    - {p.name}")

        print("\n  Analyzing cards with LLM...")
        descriptions = describe_cards(provider, sampled)

        print("\n  Synthesizing schema proposal...")
        schema = propose_schema(provider, descriptions)

        print("\n  Proposed schema:")
        print(format_schema_for_display(schema))

        choice = prompt_choice(
            "\n  [A]ccept / [E]dit in $EDITOR / [I]nline edit / [R]e-sample / [Q]uit?",
            "A/E/I/R/Q",
        )

        if choice in ("a", ""):
            return schema
        elif choice == "e":
            schema = edit_schema_in_editor(schema)
            print("\n  Updated schema:")
            print(format_schema_for_display(schema))
            confirm = prompt_choice("  Accept this schema?", "Y/n")
            if confirm in ("y", ""):
                return schema
        elif choice == "i":
            schema = edit_schema_inline(schema)
            print("\n  Updated schema:")
            print(format_schema_for_display(schema))
            confirm = prompt_choice("  Accept this schema?", "Y/n")
            if confirm in ("y", ""):
                return schema
        elif choice == "r":
            new_size = prompt_input("  Sample size", str(sample_size))
            sample_size = int(new_size)
            continue
        elif choice == "q":
            print("  Quitting.")
            sys.exit(0)


def main():
    print_header("Card Ingestion Utility")

    # ── Provider setup ──
    provider_name = prompt_input("LLM provider", "claude")
    provider = get_provider(provider_name)
    print(f"  Using provider: {provider_name}")

    # ── Step 1: Image directory ──
    print_step(1, "Locate card images")

    image_dir = prompt_input("Path to card images directory")
    images = discover_images(image_dir)

    if not images:
        print(f"  No supported images found in {image_dir}")
        sys.exit(1)

    ext_counts: dict[str, int] = {}
    for img in images:
        ext = img.suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
    ext_summary = ", ".join(f"{c} {e}" for e, c in sorted(ext_counts.items()))
    print(f"  Found {len(images)} images ({ext_summary})")

    # ── Step 2: Schema discovery ──
    print_step(2, "Schema discovery")

    output_dir = Path(image_dir)
    schema_path = output_dir / "schema.json"

    # Check for existing schema
    if schema_path.exists():
        use_existing = prompt_choice(
            f"  Found existing {schema_path.name}. Use it?", "Y/n"
        )
        if use_existing in ("y", ""):
            schema = load_schema(str(schema_path))
            print(f"  Loaded schema from {schema_path.name}")
            print(format_schema_for_display(schema))
        else:
            sample_size = int(prompt_input("  Sample size for schema discovery", "5"))
            schema = run_schema_discovery(provider, images, sample_size)
            save_schema(schema, str(schema_path))
            print(f"  Schema saved to {schema_path}")
    else:
        sample_size = int(prompt_input("  Sample size for schema discovery", "5"))
        schema = run_schema_discovery(provider, images, sample_size)
        save_schema(schema, str(schema_path))
        print(f"  Schema saved to {schema_path}")

    # ── Step 3: Card extraction ──
    print_step(3, "Card extraction")

    review_count = int(prompt_input("  Review after how many cards (0 to skip)", "3"))

    print(f"\n  Extracting {len(images)} cards...\n")
    cards, flagged = extract_batch(
        provider, images, schema, review_after=review_count
    )

    print(f"\n  Extracted: {len(cards)} cards")
    if flagged:
        print(f"  Flagged:   {len(flagged)} cards (errors during extraction)")
        show_flagged = prompt_choice("  Show flagged cards?", "Y/n")
        if show_flagged in ("y", ""):
            for f in flagged:
                print(f"    {f.get('_source_image', '?')}: {f.get('_error', '?')}")

    if not cards:
        print("  No cards extracted. Exiting.")
        sys.exit(1)

    # ── Step 4: Save output ──
    print_step(4, "Save results")

    cards_path = output_dir / "cards.json"
    save_cards(cards, str(cards_path))
    print(f"  Cards written to: {cards_path}")

    # ── Step 5: Generate parser ──
    print_step(5, "Generate card loader")

    game_name = prompt_input("  Game name (for docstring)", output_dir.name)
    loader_path = output_dir / "card_loader.py"
    generate_parser(str(cards_path), str(loader_path), game_name)
    print(f"  Loader written to: {loader_path}")

    # ── Done ──
    print_header("Done!")
    print(f"  Schema:  {schema_path}")
    print(f"  Cards:   {cards_path} ({len(cards)} cards)")
    print(f"  Loader:  {loader_path}")
    if flagged:
        print(f"  Flagged: {len(flagged)} cards need manual review")
    print()


if __name__ == "__main__":
    main()
