"""
Caylus — constants, building definitions, and helper functions.

All game data is defined here so engine.py can focus on control flow.
"""

import random
from copy import deepcopy

# ── Player Colors ────────────────────────────────────────────────────

PLAYER_COLORS = [
    {"key": "blue", "bg": "#2563eb", "light": "#93c5fd", "name": "Blue"},
    {"key": "red", "bg": "#dc2626", "light": "#fca5a5", "name": "Red"},
    {"key": "green", "bg": "#16a34a", "light": "#86efac", "name": "Green"},
    {"key": "orange", "bg": "#ea580c", "light": "#fdba74", "name": "Orange"},
    {"key": "black", "bg": "#374151", "light": "#9ca3af", "name": "Black"},
]

RESOURCE_TYPES = ["food", "wood", "stone", "cloth", "gold"]
NON_GOLD_RESOURCES = ["food", "wood", "stone", "cloth"]

# ── Castle Sections ──────────────────────────────────────────────────

CASTLE_SECTIONS = {
    "dungeon": {"name": "Dungeon", "capacity": 6, "vp_per_batch": 5},
    "walls": {"name": "Walls", "capacity": 10, "vp_per_batch": 4},
    "towers": {"name": "Towers", "capacity": 14, "vp_per_batch": 3},
}

# Bailiff positions that trigger a count if reached/passed
CASTLE_COUNT_TRIGGERS = {"dungeon": 10, "walls": 16, "towers": 22}

# ── Special Buildings ────────────────────────────────────────────────

SPECIAL_BUILDING_IDS = ["gate", "trading_post", "merchants_guild", "joust_field", "stables", "inn"]

SPECIAL_BUILDINGS = {
    "gate": {"name": "Gate", "description": "Move worker to any unoccupied space for free"},
    "trading_post": {"name": "Trading Post", "description": "Take 3 deniers from stock"},
    "merchants_guild": {"name": "Merchants' Guild", "description": "Move provost 1-3 spaces"},
    "joust_field": {"name": "Joust Field", "description": "Pay 1 denier + 1 cloth → 1 royal favor"},
    "stables": {"name": "Stables", "description": "Change turn order (up to 3 workers)", "slots": 3},
    "inn": {"name": "Inn", "description": "Pay only 1 denier per worker next turn", "slots": 2},
}

# ── Building Definitions ─────────────────────────────────────────────

NEUTRAL_BUILDINGS = [
    {"id": "n_farm", "name": "Farm", "type": "neutral", "category": "production",
     "description": "Gain 2 food OR 1 cloth",
     "effect": {"type": "choice", "options": [{"food": 2}, {"cloth": 1}]}},
    {"id": "n_sawmill", "name": "Sawmill", "type": "neutral", "category": "production",
     "description": "Gain 1 wood",
     "effect": {"type": "gain", "resources": {"wood": 1}}},
    {"id": "n_quarry", "name": "Quarry", "type": "neutral", "category": "production",
     "description": "Gain 1 stone",
     "effect": {"type": "gain", "resources": {"stone": 1}}},
    {"id": "n_carpenter", "name": "Carpenter", "type": "neutral", "category": "construction",
     "description": "Build a wood (brown) building",
     "effect": {"type": "build", "build_type": "wood"}},
    {"id": "n_market", "name": "Marketplace", "type": "neutral", "category": "marketplace",
     "description": "Sell 1 cube for 4 deniers",
     "effect": {"type": "sell", "price": 4}},
    {"id": "n_peddler", "name": "Peddler", "type": "neutral", "category": "peddler",
     "description": "Buy 1 cube (no gold) for 1 denier",
     "effect": {"type": "buy", "max": 1, "cost_per": 1}},
]

BASIC_BUILDINGS = [
    {"id": "b_peddler", "name": "Peddler", "type": "basic", "category": "peddler",
     "description": "Buy 1 cube (no gold) for 1 denier",
     "effect": {"type": "buy", "max": 1, "cost_per": 1}},
    {"id": "b_market", "name": "Marketplace", "type": "basic", "category": "marketplace",
     "description": "Sell 1 cube for 4 deniers",
     "effect": {"type": "sell", "price": 4}},
    {"id": "b_goldmine", "name": "Gold Mine", "type": "basic", "category": "production",
     "description": "Gain 1 gold",
     "effect": {"type": "gain", "resources": {"gold": 1}}},
]

WOOD_BUILDINGS = [
    {"id": "w_farm", "name": "Wood Farm", "type": "wood", "category": "production",
     "cost": {"food": 1, "wood": 1}, "vp": 2,
     "description": "Gain 2 food OR 1 cloth",
     "effect": {"type": "choice", "options": [{"food": 2}, {"cloth": 1}]}},
    {"id": "w_sawmill", "name": "Sawmill", "type": "wood", "category": "production",
     "cost": {"food": 1, "wood": 1}, "vp": 2,
     "description": "Gain 2 wood",
     "effect": {"type": "gain", "resources": {"wood": 2}}},
    {"id": "w_quarry", "name": "Quarry", "type": "wood", "category": "production",
     "cost": {"food": 1, "wood": 1}, "vp": 2,
     "description": "Gain 2 stone",
     "effect": {"type": "gain", "resources": {"stone": 2}}},
    {"id": "w_market", "name": "Market", "type": "wood", "category": "marketplace",
     "cost": {"wood": 2}, "vp": 2,
     "description": "Sell 1 cube for 6 deniers",
     "effect": {"type": "sell", "price": 6}},
    {"id": "w_peddler", "name": "Peddler", "type": "wood", "category": "peddler",
     "cost": {"food": 1, "wood": 1}, "vp": 2,
     "description": "Buy 1-2 cubes (no gold) for 2 deniers each",
     "effect": {"type": "buy", "max": 2, "cost_per": 2}},
    {"id": "w_tailor", "name": "Tailor", "type": "wood", "category": "converter",
     "cost": {"wood": 1, "cloth": 1}, "vp": 3,
     "description": "Pay 1 cloth → 2 VP, or 3 cloth → 6 VP",
     "effect": {"type": "tailor"}},
    {"id": "w_church", "name": "Church", "type": "wood", "category": "converter",
     "cost": {"stone": 2, "wood": 1}, "vp": 4, "favor_on_build": 1,
     "description": "Pay 2$ → 3 VP, or 4$ → 5 VP",
     "effect": {"type": "church"}},
    {"id": "w_lawyer", "name": "Lawyer", "type": "wood", "category": "special",
     "cost": {"stone": 1, "cloth": 1}, "vp": 3,
     "description": "Pay 1 cloth + 1$ → transform building to residential",
     "effect": {"type": "lawyer"}, "cannot_be_transformed": True},
]

STONE_BUILDINGS = [
    {"id": "s_farm", "name": "Stone Farm", "type": "stone", "category": "production",
     "cost": {"food": 1, "stone": 2}, "vp": 3,
     "description": "Gain 2 food AND 1 cloth",
     "effect": {"type": "gain", "resources": {"food": 2, "cloth": 1}},
     "owner_bonus": ["food", "cloth"]},
    {"id": "s_sawmill", "name": "Stone Sawmill", "type": "stone", "category": "production",
     "cost": {"food": 1, "stone": 2}, "vp": 3,
     "description": "Gain 2 wood AND 1 food",
     "effect": {"type": "gain", "resources": {"wood": 2, "food": 1}},
     "owner_bonus": ["wood", "food"]},
    {"id": "s_quarry", "name": "Stone Quarry", "type": "stone", "category": "production",
     "cost": {"food": 1, "stone": 2}, "vp": 3,
     "description": "Gain 2 stone AND 1 food",
     "effect": {"type": "gain", "resources": {"stone": 2, "food": 1}},
     "owner_bonus": ["stone", "food"]},
    {"id": "s_market", "name": "Stone Market", "type": "stone", "category": "marketplace",
     "cost": {"stone": 2, "wood": 1}, "vp": 3,
     "description": "Sell 1 cube for 8 deniers",
     "effect": {"type": "sell", "price": 8}},
    {"id": "s_mason", "name": "Mason", "type": "stone", "category": "construction",
     "cost": {"wood": 1, "stone": 2}, "vp": 3,
     "description": "Build a stone (gray) building",
     "effect": {"type": "build", "build_type": "stone"}},
    {"id": "s_architect", "name": "Architect", "type": "stone", "category": "construction",
     "cost": {"stone": 3}, "vp": 4,
     "description": "Build a prestige (blue) building",
     "effect": {"type": "build", "build_type": "prestige"}},
    {"id": "s_bank", "name": "Bank", "type": "stone", "category": "converter",
     "cost": {"stone": 2, "wood": 1}, "vp": 3,
     "description": "Pay 2$ → 1 gold, or 5$ → 2 gold",
     "effect": {"type": "bank"}},
    {"id": "s_alchemist", "name": "Alchemist", "type": "stone", "category": "converter",
     "cost": {"stone": 2, "cloth": 1}, "vp": 3,
     "description": "Pay 2 cubes → 1 gold, or 4 cubes → 2 gold",
     "effect": {"type": "alchemist"}},
    {"id": "s_goldmine", "name": "Gold Mine", "type": "stone", "category": "production",
     "cost": {"wood": 1, "stone": 3}, "vp": 4,
     "description": "Gain 1 gold",
     "effect": {"type": "gain", "resources": {"gold": 1}}},
]

PRESTIGE_BUILDINGS = [
    {"id": "p_statue", "name": "Statue", "type": "prestige",
     "cost": {"gold": 1, "stone": 2}, "vp": 7, "favor_on_build": 1},
    {"id": "p_theater", "name": "Theater", "type": "prestige",
     "cost": {"gold": 1, "wood": 1, "stone": 1}, "vp": 8, "favor_on_build": 1},
    {"id": "p_university", "name": "University", "type": "prestige",
     "cost": {"gold": 1, "stone": 2, "wood": 1}, "vp": 8, "favor_on_build": 1},
    {"id": "p_monument", "name": "Monument", "type": "prestige",
     "cost": {"gold": 2, "stone": 3}, "vp": 10, "favor_on_build": 2},
    {"id": "p_granary", "name": "Granary", "type": "prestige",
     "cost": {"gold": 1, "stone": 1, "wood": 1}, "vp": 6},
    {"id": "p_weaver", "name": "Weaver", "type": "prestige",
     "cost": {"gold": 1, "cloth": 1, "stone": 1}, "vp": 6},
    {"id": "p_cathedral", "name": "Cathedral", "type": "prestige",
     "cost": {"gold": 2, "stone": 3, "wood": 1}, "vp": 12},
    {"id": "p_library", "name": "Library", "type": "prestige",
     "cost": {"gold": 1, "stone": 1}, "vp": 5},
    {"id": "p_hotel", "name": "Hotel", "type": "prestige",
     "cost": {"gold": 1, "stone": 1, "wood": 1}, "vp": 5},
]

# ── Favor Tracks ─────────────────────────────────────────────────────

FAVOR_TRACKS = {
    "prestige": {
        "name": "Prestige",
        "levels": [
            {"label": "1VP", "auto": True},
            {"label": "2VP", "auto": True},
            {"label": "3VP", "auto": True},
            {"label": "4VP", "auto": True},
            {"label": "5VP", "auto": True},
        ],
    },
    "deniers": {
        "name": "Deniers",
        "levels": [
            {"label": "3$", "auto": True},
            {"label": "4$", "auto": True},
            {"label": "5$", "auto": True},
            {"label": "6$", "auto": True},
            {"label": "7$", "auto": True},
        ],
    },
    "resources": {
        "name": "Resources",
        "levels": [
            {"label": "1 food", "auto": True},
            {"label": "wood/stone", "auto": False},
            {"label": "1 cloth", "auto": True},
            {"label": "swap 1→2", "auto": False},
            {"label": "1 gold", "auto": True},
        ],
    },
    "buildings": {
        "name": "Buildings",
        "levels": [
            {"label": "—", "auto": True},
            {"label": "Carp-1", "auto": False},
            {"label": "Mason-1", "auto": False},
            {"label": "Lawyer", "auto": False},
            {"label": "Archi-1", "auto": False},
        ],
    },
}

# ── Phases ───────────────────────────────────────────────────────────

PHASES = [
    {"id": "income", "name": "1. Income"},
    {"id": "workers", "name": "2. Workers"},
    {"id": "special", "name": "3. Special"},
    {"id": "provost", "name": "4. Provost"},
    {"id": "activate", "name": "5. Activate"},
    {"id": "castle", "name": "6. Castle"},
    {"id": "end_turn", "name": "7. End Turn"},
]

ROAD_SIZE = 30  # Total road slots


# ── Helper Functions ─────────────────────────────────────────────────

def create_player(index, player_id, name):
    """Create a new player with starting resources."""
    color = PLAYER_COLORS[index % len(PLAYER_COLORS)]
    # Starting deniers: player 1 gets 5, players 2-3 get 6, players 4-5 get 7
    deniers = 5 if index == 0 else (6 if index <= 2 else 7)
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
        "deniers": deniers,
        "resources": {"food": 2, "wood": 1, "stone": 0, "cloth": 0, "gold": 0},
        "workers_total": 6,
        "workers_placed": 0,
        "houses_total": 20,
        "houses_placed": 0,
        "score": 0,
        "passed": False,
        "pass_order": -1,
        "favors": {"prestige": 0, "deniers": 0, "resources": 0, "buildings": 0},
        "inn_occupant": False,
    }


def generate_road():
    """Build the initial road: 6 shuffled neutrals + 3 basic + empty slots."""
    neutrals = deepcopy(NEUTRAL_BUILDINGS)
    random.shuffle(neutrals)
    road = []
    for i, b in enumerate(neutrals):
        road.append({"index": i, "building": b, "worker": None, "house": None})
    for i, b in enumerate(deepcopy(BASIC_BUILDINGS)):
        road.append({"index": 6 + i, "building": b, "worker": None, "house": None})
    for i in range(6 + len(BASIC_BUILDINGS), ROAD_SIZE):
        road.append({"index": i, "building": None, "worker": None, "house": None})
    return road


def create_special_state():
    """Create initial special building occupancy state."""
    return {
        "gate": {"worker": None},
        "trading_post": {"worker": None},
        "merchants_guild": {"worker": None},
        "joust_field": {"worker": None},
        "stables": [None, None, None],
        "inn": {"left": None, "right": None},
    }


def create_castle():
    """Create initial castle state."""
    return {
        "current_section": "dungeon",
        "dungeon": [None] * 6,
        "walls": [None] * 10,
        "towers": [None] * 14,
        "workers": [],
        "dungeon_counted": False,
        "walls_counted": False,
        "towers_counted": False,
    }


def create_building_stock():
    """Create the available building stock (wood, stone, prestige)."""
    return {
        "wood": deepcopy(WOOD_BUILDINGS),
        "stone": deepcopy(STONE_BUILDINGS),
        "prestige": deepcopy(PRESTIGE_BUILDINGS),
    }


def player_name(player):
    """Get display name for a player."""
    return player["name"]


def player_color_name(player):
    """Get color name for a player."""
    return player["color"]["name"]


def has_resources(player, cost):
    """Check if player can afford a resource cost dict."""
    for r, amount in cost.items():
        if player["resources"].get(r, 0) < amount:
            return False
    return True


def pay_resources(player, cost):
    """Deduct resources from player. Caller must validate first."""
    for r, amount in cost.items():
        player["resources"][r] -= amount


def gain_resources(player, resources):
    """Add resources to player."""
    for r, amount in resources.items():
        player["resources"][r] = player["resources"].get(r, 0) + amount


def get_worker_cost(state):
    """Get current worker placement cost (based on passing scale)."""
    for i, slot in enumerate(state["passing_scale"]):
        if slot is None:
            return i + 1
    return len(state["passing_scale"])


def count_residential_buildings(state, player_idx):
    """Count residential buildings owned by a player."""
    count = 0
    for slot in state["road"]:
        if (slot["building"] and
                slot["building"]["type"] == "residential" and
                slot["house"] == player_idx):
            count += 1
    return count


def player_has_building(state, player_idx, building_id):
    """Check if a player owns a specific building on the road."""
    for slot in state["road"]:
        if (slot["building"] and
                slot["building"]["id"] == building_id and
                slot["house"] == player_idx):
            return True
    return False


def get_castle_batch_options(player, state):
    """Get valid castle batch resource combos for a player.
    A batch = 1 food + 2 cubes of different types.
    Returns list of [res1, res2] pairs."""
    if player["resources"]["food"] < 1:
        return []
    others = [r for r in ["wood", "stone", "cloth", "gold"] if player["resources"][r] >= 1]
    if len(others) < 2:
        return []

    sec = state["castle"]["current_section"]
    parts = state["castle"][sec]
    has_room = any(p is None for p in parts)
    next_sec = {"dungeon": "walls", "walls": "towers"}.get(sec)
    next_has_room = next_sec and any(p is None for p in state["castle"][next_sec])
    if not has_room and not next_has_room:
        return []

    combos = []
    for i in range(len(others)):
        for j in range(i + 1, len(others)):
            combos.append([others[i], others[j]])
    return combos


def find_player_by_idx(state, idx):
    """Find player dict by index."""
    for p in state["players"]:
        if p["index"] == idx:
            return p
    return None


def get_next_active_player(state, after_idx):
    """Get next player index who hasn't passed, in turn order."""
    turn_order = state["turn_order"]
    try:
        current_pos = turn_order.index(after_idx)
    except ValueError:
        current_pos = 0
    n = len(turn_order)
    for i in range(1, n + 1):
        next_pos = (current_pos + i) % n
        next_idx = turn_order[next_pos]
        p = find_player_by_idx(state, next_idx)
        if p and not p["passed"]:
            return next_idx
    return -1


def all_players_passed(state):
    """Check if all players have passed."""
    return all(p["passed"] for p in state["players"])


def return_worker(state, player_idx):
    """Return a placed worker to a player's supply."""
    p = find_player_by_idx(state, player_idx)
    if p:
        p["workers_placed"] = max(0, p["workers_placed"] - 1)


def can_afford_with_discount(player, cost, discount=1):
    """Check if player can afford a building cost with a 1-resource discount."""
    cost_copy = dict(cost)
    # Remove 1 from the most expensive resource
    for r, a in sorted(cost_copy.items(), key=lambda x: x[1], reverse=True):
        if a > 0:
            cost_copy[r] = a - 1
            break
    return all(player["resources"].get(r, 0) >= a for r, a in cost_copy.items() if a > 0), cost_copy


def apply_discounted_cost(player, cost, discount=1):
    """Pay building cost with discount. Returns the actual cost paid."""
    cost_copy = dict(cost)
    for r, a in sorted(cost_copy.items(), key=lambda x: x[1], reverse=True):
        if a > 0:
            cost_copy[r] = a - 1
            break
    for r, a in cost_copy.items():
        if a > 0:
            player["resources"][r] -= a
    return cost_copy
