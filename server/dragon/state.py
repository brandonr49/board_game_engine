"""
Constants and state helpers for In the Year of the Dragon.
Direct port of the JSX config data + utility functions.
"""

import random
from copy import deepcopy

# ── Person Types ─────────────────────────────────────────────────────

PERSON_TYPES = {
    "monk": {
        "name": "Monk", "color": "#8B4513", "icon": "☸️",
        "resource": "buddha", "resource_icon": "☸️",
        "young": {"symbols": 1, "value": 6},
        "old":   {"symbols": 2, "value": 2},
        "young_only": False,
    },
    "healer": {
        "name": "Healer", "color": "#3498db", "icon": "⚕️",
        "resource": "mortar", "resource_icon": "⚗️",
        "young": {"symbols": 1, "value": 4},
        "old":   {"symbols": 2, "value": 1},
        "young_only": False,
    },
    "pyrotechnist": {
        "name": "Pyrotechnist", "color": "#8e44ad", "icon": "🎆",
        "resource": "rocket", "resource_icon": "🚀",
        "young": {"symbols": 1, "value": 5},
        "old":   {"symbols": 2, "value": 3},
        "young_only": False,
    },
    "craftsman": {
        "name": "Craftsman", "color": "#d4a574", "icon": "🔨",
        "resource": "hammer", "resource_icon": "🔨",
        "young": {"symbols": 1, "value": 2},
        "old":   None,
        "young_only": True,
    },
    "courtLady": {
        "name": "Court Lady", "color": "#d4a017", "icon": "🪭",
        "resource": "dragon", "resource_icon": "🐉",
        "young": {"symbols": 1, "value": 1},
        "old":   None,
        "young_only": True,
    },
    "taxCollector": {
        "name": "Tax Collector", "color": "#f1c40f", "icon": "💰",
        "resource": "coin", "resource_icon": "🪙",
        "young": {"symbols": 3, "value": 3},
        "old":   None,
        "young_only": True,
    },
    "warrior": {
        "name": "Warrior", "color": "#c0392b", "icon": "⚔️",
        "resource": "helmet", "resource_icon": "🪖",
        "young": {"symbols": 1, "value": 5},
        "old":   {"symbols": 2, "value": 3},
        "young_only": False,
    },
    "scholar": {
        "name": "Scholar", "color": "#ecf0f1", "icon": "📜",
        "resource": "book", "resource_icon": "📖",
        "young": {"symbols": 2, "value": 4},
        "old":   {"symbols": 3, "value": 2},
        "young_only": False,
    },
    "farmer": {
        "name": "Farmer", "color": "#27ae60", "icon": "🌾",
        "resource": "rice", "resource_icon": "🌾",
        "young": {"symbols": 1, "value": 4},
        "old":   {"symbols": 2, "value": 1},
        "young_only": False,
    },
}

# ── Action Info ──────────────────────────────────────────────────────

ACTION_INFO = {
    "taxes":     {"name": "Taxes",             "icon": "💰", "bonus": "taxCollector",  "unit": "¥"},
    "build":     {"name": "Build",             "icon": "🏗️", "bonus": "craftsman",     "unit": "floors"},
    "harvest":   {"name": "Harvest",           "icon": "🌾", "bonus": "farmer",        "unit": "rice"},
    "fireworks": {"name": "Fireworks Display",  "icon": "🎆", "bonus": "pyrotechnist",  "unit": "fireworks"},
    "military":  {"name": "Military Parade",   "icon": "⚔️", "bonus": "warrior",       "unit": "steps"},
    "research":  {"name": "Research",          "icon": "📜", "bonus": "scholar",        "unit": "VP"},
    "privilege": {"name": "Privilege",         "icon": "🏅", "bonus": None,             "unit": ""},
}

ACTION_IDS = ["taxes", "build", "harvest", "fireworks", "military", "research", "privilege"]

# ── Event Types ──────────────────────────────────────────────────────

EVENT_TYPES = [
    {"id": "peace",           "name": "Peace",            "icon": "☮️",  "color": "#27ae60"},
    {"id": "drought",         "name": "Drought",          "icon": "☀️",  "color": "#e67e22"},
    {"id": "contagion",       "name": "Contagion",        "icon": "☠️",  "color": "#8e44ad"},
    {"id": "mongolInvasion",  "name": "Mongol Invasion",  "icon": "🏇",  "color": "#c0392b"},
    {"id": "imperialTribute", "name": "Imperial Tribute",  "icon": "👑",  "color": "#f1c40f"},
    {"id": "dragonFestival",  "name": "Dragon Festival",  "icon": "🐉",  "color": "#e74c3c"},
]

PLAYER_COLORS = [
    {"name": "Red",    "primary": "#b33025", "light": "#e8453a", "dark": "#7a1f17"},
    {"name": "Blue",   "primary": "#2563a8", "light": "#3b82d6", "dark": "#1a4270"},
    {"name": "Green",  "primary": "#1d8348", "light": "#28a85c", "dark": "#145a32"},
    {"name": "Yellow", "primary": "#c49000", "light": "#e8ad10", "dark": "#8a6500"},
    {"name": "Purple", "primary": "#7b3fa0", "light": "#9b59b6", "dark": "#5b2d75"},
]


# ── Utility Functions ────────────────────────────────────────────────

def count_symbols(player, type_id):
    """Count total resource symbols of a given person type across all palaces."""
    total = 0
    for palace in player["palaces"]:
        for person in palace["persons"]:
            if person["type_id"] == type_id:
                total += person["symbols"]
    return total


def get_person_track_order(players):
    """
    Return player indices sorted by person track (descending), 
    with higher index as tiebreaker.
    """
    indices = list(range(len(players)))
    indices.sort(key=lambda i: (players[i]["person_track"], i), reverse=True)
    return indices


def combo_key(a, b):
    """Canonical key for a pair of type IDs (order-independent)."""
    return "+".join(sorted([a, b]))


# ── Tile Generation ──────────────────────────────────────────────────

def generate_event_tiles():
    """Generate the 12-month event track: 2 peace + 10 shuffled non-peace."""
    events = [
        {**EVENT_TYPES[0], "slot": 0},
        {**EVENT_TYPES[0], "slot": 1},
    ]

    non_peace = EVENT_TYPES[1:]
    pool = []
    for e in non_peace:
        pool.append({**e})
        pool.append({**e})
    random.shuffle(pool)

    # Avoid consecutive same events
    placed = []
    deferred = []
    for tile in pool:
        if placed and placed[-1]["id"] == tile["id"]:
            deferred.append(tile)
        else:
            placed.append(tile)

    for tile in deferred:
        inserted = False
        for i in range(len(placed) + 1):
            prev_id = placed[i - 1]["id"] if i > 0 else None
            next_id = placed[i]["id"] if i < len(placed) else None
            if prev_id != tile["id"] and next_id != tile["id"]:
                placed.insert(i, tile)
                inserted = True
                break
        if not inserted:
            placed.append(tile)

    for i, t in enumerate(placed):
        events.append({**t, "slot": i + 2})

    return events


def generate_person_tiles(player_count):
    """Generate the pool of person tiles scaled to player count."""
    tiles = []
    tile_id = 0

    for type_id, ptype in PERSON_TYPES.items():
        if ptype["young_only"]:
            for i in range(player_count * 2):
                tiles.append({
                    "id": f"{type_id}-young-{i}",
                    "type_id": type_id,
                    "experience": "young",
                    "symbols": ptype["young"]["symbols"],
                    "value": ptype["young"]["value"],
                })
        else:
            old_count = max(0, 4 - (5 - player_count))
            young_count = max(0, 6 - (5 - player_count))
            for i in range(old_count):
                tiles.append({
                    "id": f"{type_id}-old-{i}",
                    "type_id": type_id,
                    "experience": "old",
                    "symbols": ptype["old"]["symbols"],
                    "value": ptype["old"]["value"],
                })
            for i in range(young_count):
                tiles.append({
                    "id": f"{type_id}-young-{i}",
                    "type_id": type_id,
                    "experience": "young",
                    "symbols": ptype["young"]["symbols"],
                    "value": ptype["young"]["value"],
                })

    return tiles


def create_player(index, player_id, name):
    """Create a fresh player state."""
    cards = [{"type_id": tid, "is_wild": False} for tid in PERSON_TYPES]
    cards.append({"type_id": None, "is_wild": True})
    cards.append({"type_id": None, "is_wild": True})

    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": PLAYER_COLORS[index],
        "palaces": [
            {"floors": 2, "persons": []},
            {"floors": 2, "persons": []},
        ],
        "yuan": 6,
        "rice": 0,
        "fireworks": 0,
        "privileges": {"small": 0, "large": 0},
        "person_track": 0,
        "scoring_track": 0,
        "cards": cards,
    }


def deal_action_groups(player_count):
    """Shuffle action types into groups, one per player."""
    shuffled = ACTION_IDS[:]
    random.shuffle(shuffled)
    groups = [[] for _ in range(player_count)]
    for i, action_id in enumerate(shuffled):
        groups[i % player_count].append(action_id)
    return groups


# ── Action Execution ─────────────────────────────────────────────────

def execute_taxes(player):
    bonus = count_symbols(player, "taxCollector")
    total = 2 + bonus
    player["yuan"] += total
    return f"Collected {total}¥ (2 base + {bonus} tax collectors). Now {player['yuan']}¥."


def execute_harvest(player):
    bonus = count_symbols(player, "farmer")
    total = 1 + bonus
    player["rice"] += total
    return f"Harvested {total} rice (1 base + {bonus} farmers). Now {player['rice']} rice."


def execute_fireworks(player):
    bonus = count_symbols(player, "pyrotechnist")
    total = 1 + bonus
    player["fireworks"] += total
    return f"Gained {total} fireworks (1 base + {bonus} pyrotechnists). Now {player['fireworks']}."


def execute_military(player):
    bonus = count_symbols(player, "warrior")
    total = 1 + bonus
    player["person_track"] += total
    return f"Advanced {total} steps (1 base + {bonus} warriors). Now at {player['person_track']}."


def execute_research(player):
    bonus = count_symbols(player, "scholar")
    total = 1 + bonus
    player["scoring_track"] += total
    return f"Gained {total} VP (1 base + {bonus} scholars). Now {player['scoring_track']} VP."


def execute_build(player, placement):
    """
    Apply a build action with explicit placement.
    placement is a list of dicts: [{"palace_index": 0, "floors": 1}, {"palace_index": "new", "floors": 2}]
    Returns log string.
    """
    bonus = count_symbols(player, "craftsman")
    total = 1 + bonus

    # Validate total floors in placement matches expected
    placed = sum(p["floors"] for p in placement)
    if placed != total:
        raise ValueError(f"Build placement must use exactly {total} floors, got {placed}")

    for entry in placement:
        if entry["palace_index"] == "new":
            if entry["floors"] < 1 or entry["floors"] > 3:
                raise ValueError("New palace must have 1-3 floors")
            player["palaces"].append({"floors": entry["floors"], "persons": []})
        else:
            idx = entry["palace_index"]
            if idx < 0 or idx >= len(player["palaces"]):
                raise ValueError(f"Invalid palace index {idx}")
            palace = player["palaces"][idx]
            if palace["floors"] + entry["floors"] > 3:
                raise ValueError(f"Palace {idx} would exceed 3 floors")
            palace["floors"] += entry["floors"]

    return f"Built {total} floor(s) (1 base + {bonus} craftsmen)."


def execute_build_auto(player):
    """
    Fallback auto-build: fills existing palaces first, then creates new ones.
    Used when we want a simple default. Returns (log_string, resulting_palaces).
    """
    bonus = count_symbols(player, "craftsman")
    total = 1 + bonus
    remaining = total

    for palace in player["palaces"]:
        if remaining <= 0:
            break
        add = min(3 - palace["floors"], remaining)
        palace["floors"] += add
        remaining -= add

    while remaining > 0:
        floors = min(3, remaining)
        player["palaces"].append({"floors": floors, "persons": []})
        remaining -= floors

    return f"Built {total} floor(s) (1 base + {bonus} craftsmen)."


def execute_privilege(player, size):
    if size == "small":
        if player["yuan"] < 2:
            raise ValueError("Not enough yuan for small privilege")
        player["yuan"] -= 2
        player["privileges"]["small"] += 1
        return f"Bought small privilege (2¥). {player['yuan']}¥ left."
    elif size == "large":
        if player["yuan"] < 7:
            raise ValueError("Not enough yuan for large privilege")
        player["yuan"] -= 7
        player["privileges"]["large"] += 1
        return f"Bought large privilege (7¥). {player['yuan']}¥ left."
    else:
        raise ValueError(f"Invalid privilege size: {size}")


# ── Decay ────────────────────────────────────────────────────────────

def apply_decay(players, log):
    """Empty palaces lose a floor; palaces at 0 floors are removed."""
    for p in players:
        new_palaces = []
        for pal in p["palaces"]:
            if pal["persons"] == [] and pal["floors"] > 0:
                log.append(f"{p['name']}: empty palace decays.")
                pal["floors"] -= 1
            if pal["floors"] > 0:
                new_palaces.append(pal)
        p["palaces"] = new_palaces
