"""TZAAR board geometry, movement, setup, and win detection."""

import random

# ── Constants ─────────────────────────────────────────

PIECE_TYPES = ["tzaar", "tzarra", "tott"]
PIECES_PER_PLAYER = {"tzaar": 6, "tzarra": 9, "tott": 15}
BOARD_MAX_RADIUS = 4

AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

# Type display labels
TYPE_LABELS = {"tzaar": "Z", "tzarra": "A", "tott": "T"}


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def hex_distance(q, r):
    """Distance from center (0,0)."""
    return max(abs(q), abs(r), abs(q + r))


def is_valid(q, r):
    """On the board: distance 1-4 from center (no center space)."""
    d = hex_distance(q, r)
    return 1 <= d <= BOARD_MAX_RADIUS


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "q,r" -> None for all 60 positions."""
    board = {}
    for q in range(-BOARD_MAX_RADIUS, BOARD_MAX_RADIUS + 1):
        for r in range(-BOARD_MAX_RADIUS, BOARD_MAX_RADIUS + 1):
            if is_valid(q, r):
                board[hex_key(q, r)] = None
    return board


def all_positions():
    """Return list of all valid (q, r) tuples."""
    return [(q, r) for q in range(-BOARD_MAX_RADIUS, BOARD_MAX_RADIUS + 1)
            for r in range(-BOARD_MAX_RADIUS, BOARD_MAX_RADIUS + 1)
            if is_valid(q, r)]


ALL_POSITIONS = all_positions()


# ── Setup ─────────────────────────────────────────────

def setup_random(board):
    """Randomly assign 30 white + 30 black pieces to the 60 spaces."""
    pieces = []
    for color in ("white", "black"):
        for ptype, count in PIECES_PER_PLAYER.items():
            for _ in range(count):
                pieces.append({"color": color, "type": ptype, "height": 1})

    positions = list(board.keys())
    random.shuffle(pieces)
    for i, key in enumerate(positions):
        board[key] = pieces[i]


def setup_fixed(board):
    """Fixed starting position — alternating colors in concentric rings.
    Inner ring (dist 1): alternating tzaars
    Ring 2: alternating tzarras
    Ring 3: alternating totts
    Ring 4: alternating totts
    """
    rings = {1: [], 2: [], 3: [], 4: []}
    for q, r in ALL_POSITIONS:
        d = hex_distance(q, r)
        rings[d].append(hex_key(q, r))

    # Sort each ring for deterministic alternation
    for d in rings:
        rings[d].sort()

    type_map = {1: "tzaar", 2: "tzarra", 3: "tott", 4: "tott"}

    for d, keys in rings.items():
        ptype = type_map[d]
        for i, key in enumerate(keys):
            color = "white" if i % 2 == 0 else "black"
            board[key] = {"color": color, "type": ptype, "height": 1}


# ── Movement / targeting ─────────────────────────────

def find_line_target(board, from_key, dq, dr):
    """Move in direction (dq, dr) from from_key over empty spaces.
    Return the key of the first occupied space, or None if line goes off board.
    Cannot cross center (0,0) which doesn't exist as a position."""
    q, r = parse_hex(from_key)

    while True:
        q += dq
        r += dr

        # Check if we hit the center (0,0) — blocked
        if q == 0 and r == 0:
            return None

        key = hex_key(q, r)

        if key not in board:
            # Off the board
            return None

        if board[key] is not None:
            # Found an occupied space
            return key

        # Empty space — continue


def find_captures(board, player_color):
    """Find all valid capture moves for player_color.
    Returns list of {"from": key, "to": key}."""
    opp_color = "black" if player_color == "white" else "white"
    captures = []

    for key, piece in board.items():
        if piece is None or piece["color"] != player_color:
            continue

        for dq, dr in AXIAL_DIRS:
            target_key = find_line_target(board, key, dq, dr)
            if target_key is None:
                continue
            target = board[target_key]
            if target["color"] == opp_color and piece["height"] >= target["height"]:
                captures.append({"from": key, "to": target_key})

    return captures


def find_stacks(board, player_color):
    """Find all valid stacking moves for player_color.
    Returns list of {"from": key, "to": key}."""
    stacks = []

    for key, piece in board.items():
        if piece is None or piece["color"] != player_color:
            continue

        for dq, dr in AXIAL_DIRS:
            target_key = find_line_target(board, key, dq, dr)
            if target_key is None:
                continue
            target = board[target_key]
            if target["color"] == player_color:
                stacks.append({"from": key, "to": target_key})

    return stacks


# ── Win condition ─────────────────────────────────────

def check_loss(board, color):
    """Check if 'color' has lost — missing any piece type on the board.
    Only the TOP piece of a stack counts for type."""
    type_counts = {t: 0 for t in PIECE_TYPES}

    for piece in board.values():
        if piece is not None and piece["color"] == color:
            type_counts[piece["type"]] += 1

    return any(count == 0 for count in type_counts.values())


def get_type_counts(board, color):
    """Count visible types for a color (top of stacks only)."""
    counts = {t: 0 for t in PIECE_TYPES}
    for piece in board.values():
        if piece is not None and piece["color"] == color:
            counts[piece["type"]] += 1
    return counts


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    color = "white" if index == 0 else "black"
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
    }
