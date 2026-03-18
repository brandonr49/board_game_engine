"""
Lost Cities – constants, card generation, and scoring helpers.

5 expeditions (colors), each with:
  - 3 wager cards (value 0, displayed as handshake)
  - 9 expedition cards (values 2–10)
= 60 cards total.  2 players, 8-card hands.
"""

import random

EXPEDITIONS = ["yellow", "blue", "white", "green", "red"]

EXPEDITION_NAMES = {
    "yellow": "Desert",
    "blue": "Sea",
    "white": "Himalayas",
    "green": "Rainforest",
    "red": "Volcano",
}

EXPEDITION_COLORS = {
    "yellow": "#e6a817",
    "blue":   "#2980b9",
    "white":  "#bdc3c7",
    "green":  "#27ae60",
    "red":    "#c0392b",
}

HAND_SIZE = 8
EXPEDITION_COST = 20
BONUS_THRESHOLD = 8
BONUS_POINTS = 20


def generate_deck():
    """Return a shuffled list of all 60 cards."""
    cards = []
    for exp in EXPEDITIONS:
        # 3 wager cards per expedition
        for i in range(3):
            cards.append({"expedition": exp, "value": 0, "id": f"{exp}_w{i}"})
        # expedition cards 2–10
        for v in range(2, 11):
            cards.append({"expedition": exp, "value": v, "id": f"{exp}_{v}"})
    random.shuffle(cards)
    return cards


def create_player(index, player_id, name):
    """Create initial player state."""
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "hand": [],
        "expeditions": {exp: [] for exp in EXPEDITIONS},
    }


def score_expedition(cards):
    """Score a single expedition column.

    - If no cards played: 0 points (no cost).
    - Otherwise: (sum of values - 20) * (1 + wager_count).
    - If 8+ cards: +20 bonus (applied after multiplier).
    """
    if not cards:
        return {"subtotal": 0, "wager_count": 0, "multiplier": 1,
                "result": 0, "bonus": 0, "total": 0, "card_count": 0}

    wager_count = sum(1 for c in cards if c["value"] == 0)
    card_sum = sum(c["value"] for c in cards)
    subtotal = card_sum - EXPEDITION_COST
    multiplier = 1 + wager_count
    result = subtotal * multiplier
    bonus = BONUS_POINTS if len(cards) >= BONUS_THRESHOLD else 0
    total = result + bonus

    return {
        "subtotal": subtotal,
        "wager_count": wager_count,
        "multiplier": multiplier,
        "result": result,
        "bonus": bonus,
        "total": total,
        "card_count": len(cards),
    }


def score_player(player):
    """Score all expeditions for a player. Returns {expedition_scores, total}."""
    expedition_scores = {}
    total = 0
    for exp in EXPEDITIONS:
        s = score_expedition(player["expeditions"][exp])
        expedition_scores[exp] = s
        total += s["total"]
    return {"expedition_scores": expedition_scores, "total": total}


def can_place_card(expedition_cards, card):
    """Check if a card can be legally placed on an expedition column.

    Wager cards (value 0) can only be placed if no number cards exist yet.
    Number cards must be strictly higher than the last number card.
    """
    if card["value"] == 0:
        # Wager cards only before any numbered cards
        return all(c["value"] == 0 for c in expedition_cards)
    if not expedition_cards:
        return True
    last_value = max((c["value"] for c in expedition_cards), default=0)
    # last numbered card value must be less than new card
    # (wager cards have value 0, so any numbered card > 0 is fine after wagers)
    return card["value"] > last_value
