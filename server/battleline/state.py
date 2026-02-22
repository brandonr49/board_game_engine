"""
Constants and state helpers for Battle Line.

Cards, deck generation, player creation, and win-condition checking.
"""

import random
from copy import deepcopy

# ── Card Constants ────────────────────────────────────────────────────

TROOP_COLORS = ("red", "blue", "yellow", "green", "purple", "orange")

TACTICS_CARDS = {
    # Leaders (morale / wild) — any color, any value 1-10
    "alexander":          {"type": "tactics", "subtype": "leader", "name": "Alexander"},
    "darius":             {"type": "tactics", "subtype": "leader", "name": "Darius"},
    # Morale — wild with constraints
    "companion_cavalry":  {"type": "tactics", "subtype": "morale", "name": "Companion Cavalry",
                           "wild_value": 8, "wild_color": "any"},
    "shield_bearers":     {"type": "tactics", "subtype": "morale", "name": "Shield Bearers",
                           "wild_value_max": 3, "wild_color": "any"},
    # Environment
    "fog":                {"type": "tactics", "subtype": "environment", "name": "Fog"},
    "mud":                {"type": "tactics", "subtype": "environment", "name": "Mud"},
    # Guile
    "scout":              {"type": "tactics", "subtype": "guile", "name": "Scout"},
    "redeploy":           {"type": "tactics", "subtype": "guile", "name": "Redeploy"},
    "deserter":           {"type": "tactics", "subtype": "guile", "name": "Deserter"},
    "traitor":            {"type": "tactics", "subtype": "guile", "name": "Traitor"},
}

NUM_FLAGS = 9


# ── Deck Generation ──────────────────────────────────────────────────

def generate_troop_deck():
    """Return a shuffled deck of 60 troop cards."""
    deck = []
    for color in TROOP_COLORS:
        for value in range(1, 11):
            deck.append({"type": "troop", "color": color, "value": value})
    random.shuffle(deck)
    return deck


def generate_tactics_deck():
    """Return a shuffled deck of 10 tactics cards."""
    deck = []
    for card_id, info in TACTICS_CARDS.items():
        card = dict(info)
        card["id"] = card_id
        deck.append(card)
    random.shuffle(deck)
    return deck


# ── Player / State Creation ──────────────────────────────────────────

def create_player(index, player_id, name):
    """Create initial player state."""
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "hand": [],
        "tactics_played": 0,
        "has_leader_on_board": False,
    }


def create_initial_state(player_ids, player_names):
    """Build the full initial game state for a 2-player Battle Line game."""
    troop_deck = generate_troop_deck()
    tactics_deck = generate_tactics_deck()

    players = []
    for i, (pid, name) in enumerate(zip(player_ids, player_names)):
        p = create_player(i, pid, name)
        # Deal 7 troop cards to each player
        for _ in range(7):
            p["hand"].append(troop_deck.pop())
        players.append(p)

    flags = []
    for _ in range(NUM_FLAGS):
        flags.append({
            "claimed_by": None,
            "slots": [[], []],          # per-player card lists
            "environment": [],          # fog / mud names
            "completion_turn": [None, None],
        })

    return {
        "game": "battleline",
        "player_ids": list(player_ids),
        "players": players,
        "flags": flags,
        "troop_deck": troop_deck,
        "tactics_deck": tactics_deck,
        "discard": [[], []],            # per-player visible discard piles
        "current_player": 0,
        "turn_number": 0,
        "phase": "play_card",
        "sub_phase": None,
        "scout_state": None,
        "redeploy_state": None,
        "traitor_state": None,
        "log": [],
        "winner": None,
    }


# ── Query Helpers ─────────────────────────────────────────────────────

def get_available_troops(state):
    """
    Return the set of (color, value) troop tuples NOT visible on the board
    or in discard piles.  Used for claim-proof: the pool of cards that
    *could* still complete an opponent's formation.

    Per rules, hands and deck contents are NOT subtracted (private info).
    """
    all_troops = {(c, v) for c in TROOP_COLORS for v in range(1, 11)}
    visible = set()

    # Cards on flags
    for flag in state["flags"]:
        for side in flag["slots"]:
            for card in side:
                if card["type"] == "troop":
                    visible.add((card["color"], card["value"]))

    # Discard piles
    for pile in state["discard"]:
        for card in pile:
            if card["type"] == "troop":
                visible.add((card["color"], card["value"]))

    return all_troops - visible


def _flag_card_count(flag, player_idx):
    """How many cards does a player need on this flag (3, or 4 with mud)."""
    has_mud = "mud" in flag["environment"]
    return 4 if has_mud else 3


def check_win_condition(state):
    """
    Return the winning player index, or None.

    Win conditions:
    - Breakthrough: 3 adjacent claimed flags
    - Envelopment: 5 total claimed flags
    """
    for player_idx in range(2):
        # Envelopment: 5 flags
        claimed = [i for i, f in enumerate(state["flags"]) if f["claimed_by"] == player_idx]
        if len(claimed) >= 5:
            return player_idx

        # Breakthrough: 3 adjacent flags
        consecutive = 0
        for i in range(NUM_FLAGS):
            if state["flags"][i]["claimed_by"] == player_idx:
                consecutive += 1
                if consecutive >= 3:
                    return player_idx
            else:
                consecutive = 0

    return None
