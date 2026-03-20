# Card Ingestion Utility

Extract structured card data from board game card images using vision LLMs.

## Setup

```bash
pip install -r tools/requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

## Usage

```bash
# From the repo root:
python -m tools.card_ingest
```

The interactive CLI walks you through:

1. **Image directory** — point it at a folder of card images (jpg, png, webp, etc.)
2. **Schema discovery** — samples a few cards, proposes a JSON schema, you review/edit
3. **Batch extraction** — extracts structured data from every card image
4. **Output** — writes `cards.json` and `card_loader.py` to the image directory

## Output Files

- `schema.json` — the confirmed card schema (reusable on re-runs)
- `cards.json` — array of extracted card objects
- `card_loader.py` — minimal Python module to load and filter cards

## Using in a Game Engine

```python
# In your server/<game>/state.py:
from card_loader import load_cards, get_cards_by_type, generate_deck

ALL_CARDS = load_cards("path/to/cards.json")
TROOP_CARDS = get_cards_by_type(ALL_CARDS, "troop")

def create_deck():
    return generate_deck(ALL_CARDS, card_types=["troop"], shuffle=True)
```

## Swapping LLM Providers

The default provider is Claude (via Anthropic API). To use a different model:

1. Subclass `LLMProvider` in `llm_provider.py`
2. Implement `analyze_image(image_path, prompt)` and `analyze_text(prompt)`
3. Register it in `get_provider()`

See the commented stubs in `llm_provider.py` for Ollama, llama.cpp, and OpenAI-compatible examples.

## Re-running

If `schema.json` already exists in the image directory, the tool will offer to reuse it — useful for re-extracting after fixing images or tweaking prompts.
