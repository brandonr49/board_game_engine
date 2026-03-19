"""TAMSK board game — constants, hex math, and board generation."""

import random

# ── Constants ────────────────────────────────────────────
RINGS_PER_PLAYER = 32
HOURGLASS_TIMER_SECS = 180  # 3 minutes
PRESSURE_TIMER_SECS = 15

BOARD_RADIUS = 3

# Corner positions (hex vertices) — hourglass starting spots.
# Ordered for alternating placement: black, red, black, red, black, red.
CORNER_POSITIONS = [
    (3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3)
]

# Axial hex direction vectors (flat-top)
HEX_DIRECTIONS = [
    (1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)
]


# ── Hex coordinate helpers ───────────────────────────────

def hex_key(q, r):
    """Serialize axial coords to string key."""
    return f"{q},{r}"


def parse_hex(key):
    """Deserialize string key to (q, r) tuple."""
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def hex_distance(q1, r1, q2, r2):
    """Cube-coordinate distance between two axial hex positions."""
    dq = q1 - q2
    dr = r1 - r2
    return max(abs(dq), abs(dr), abs(dq + dr))


def is_valid_position(q, r):
    """Check if (q, r) is on the board (radius 3 hex)."""
    return hex_distance(0, 0, q, r) <= BOARD_RADIUS


def hex_neighbors(q, r):
    """Return list of adjacent (q, r) positions that are on the board."""
    result = []
    for dq, dr in HEX_DIRECTIONS:
        nq, nr = q + dq, r + dr
        if is_valid_position(nq, nr):
            result.append((nq, nr))
    return result


def ring_capacity(q, r):
    """Ring capacity of a board space based on distance from center."""
    dist = hex_distance(0, 0, q, r)
    if dist == 0:
        return 4
    elif dist == 1:
        return 3
    elif dist == 2:
        return 2
    else:
        return 1


# ── Board and player generation ──────────────────────────

def generate_board():
    """Generate the 37-space hex board as a dict keyed by "q,r"."""
    board = {}
    for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
        for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            if is_valid_position(q, r):
                board[hex_key(q, r)] = {
                    "capacity": ring_capacity(q, r),
                    "rings": [],  # list of player colors who placed rings here
                }
    return board


def create_player(index, player_id, name):
    """Create a player state dict."""
    color = "black" if index == 0 else "red"
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
        "rings_remaining": RINGS_PER_PLAYER,
        "passed": False,
    }


def create_hourglass(hid, color, position_key):
    """Create an hourglass state dict."""
    return {
        "id": hid,
        "color": color,
        "position": position_key,
        "timer_remaining": HOURGLASS_TIMER_SECS,
        "timer_started_at": None,
        "is_dead": False,
    }


def setup_hourglasses():
    """Create the 6 hourglasses in alternating corner positions.

    Order: black_0 at corner 0, red_0 at corner 1, black_1 at corner 2, etc.
    """
    hourglasses = {}
    for i, (q, r) in enumerate(CORNER_POSITIONS):
        color = "black" if i % 2 == 0 else "red"
        color_idx = i // 2
        hid = f"{color}_{color_idx}"
        hourglasses[hid] = create_hourglass(hid, color, hex_key(q, r))
    return hourglasses


def get_player_hourglasses(hourglasses, color):
    """Return list of hourglass dicts belonging to the given color."""
    return [h for h in hourglasses.values() if h["color"] == color]


def get_hourglass_at(hourglasses, position_key):
    """Return the hourglass at a position, or None."""
    for h in hourglasses.values():
        if h["position"] == position_key and not h.get("removed", False):
            return h
    return None
