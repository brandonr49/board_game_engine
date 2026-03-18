"""
Constants and state helpers for Arboretum.

Cards, deck generation, grid helpers, and initial state creation.
"""

import random
from copy import deepcopy

# ── Species Constants ────────────────────────────────────────────────

SPECIES = [
    {"id": "cassia",           "name": "Cassia",           "color": "#f4d03f"},
    {"id": "blue_spruce",      "name": "Blue Spruce",      "color": "#5dade2"},
    {"id": "dogwood",          "name": "Dogwood",          "color": "#f5b7b1"},
    {"id": "jacaranda",        "name": "Jacaranda",        "color": "#a569bd"},
    {"id": "maple",            "name": "Maple",            "color": "#e74c3c"},
    {"id": "oak",              "name": "Oak",              "color": "#784212"},
    {"id": "cherry_blossom",   "name": "Cherry Blossom",   "color": "#ff69b4"},
    {"id": "royal_poinciana",  "name": "Royal Poinciana",  "color": "#e67e22"},
    {"id": "tulip_poplar",     "name": "Tulip Poplar",     "color": "#27ae60"},
    {"id": "willow",           "name": "Willow",           "color": "#76d7c4"},
]

VALUES = list(range(1, 9))  # 1-8
HAND_SIZE = 7
GRID_SIZE = 9
GRID_CENTER = (4, 4)

# How many species to use based on player count
SPECIES_COUNT_BY_PLAYERS = {2: 6, 3: 8, 4: 10}


# ── Grid Helpers ─────────────────────────────────────────────────────

def pos_key(row, col):
    """Create a string key for a grid position."""
    return f"{row},{col}"


def parse_key(key):
    """Parse a grid key back to (row, col) tuple."""
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def get_neighbors(row, col):
    """Return orthogonal neighbors as (row, col) tuples."""
    return [
        (row - 1, col),
        (row + 1, col),
        (row, col - 1),
        (row, col + 1),
    ]


def get_valid_placements(grid):
    """
    Return list of (row, col) positions where a card can be placed.
    If grid is empty, only the center is valid.
    Otherwise, any empty cell orthogonally adjacent to an existing card.
    """
    if not grid:
        return [GRID_CENTER]

    valid = set()
    for key in grid:
        row, col = parse_key(key)
        for nr, nc in get_neighbors(row, col):
            nkey = pos_key(nr, nc)
            if nkey not in grid and 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                valid.add((nr, nc))
    return sorted(valid)


# ── Deck Generation ──────────────────────────────────────────────────

def generate_deck(active_species):
    """Generate and shuffle a deck for the given species list."""
    deck = []
    for species in active_species:
        for value in VALUES:
            deck.append({
                "species": species["id"],
                "value": value,
            })
    random.shuffle(deck)
    return deck


# ── State Creation ───────────────────────────────────────────────────

def create_initial_state(player_ids, player_names):
    """Build the full initial game state for an Arboretum game."""
    player_count = len(player_ids)
    species_count = SPECIES_COUNT_BY_PLAYERS[player_count]
    active_species = random.sample(SPECIES, species_count)
    deck = generate_deck(active_species)

    players = []
    for i, (pid, name) in enumerate(zip(player_ids, player_names)):
        hand = []
        for _ in range(HAND_SIZE):
            hand.append(deck.pop())
        players.append({
            "index": i,
            "player_id": pid,
            "name": name,
            "hand": hand,
            "discard": [],
            "grid": {},
        })

    return {
        "game": "arboretum",
        "player_ids": list(player_ids),
        "player_count": player_count,
        "players": players,
        "active_species": active_species,
        "draw_pile": deck,
        "draw_pile_count": len(deck),
        "current_player": 0,
        "turn_number": 0,
        "phase": "draw1",
        "draw_state": {"cards_drawn": 0, "first_drawn_card": None},
        "winner": None,
        "game_over": False,
        "scoring_results": None,
    }
