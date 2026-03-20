"""LYNGK board geometry, stacking, movement, and scoring."""

import random

# ── Constants ─────────────────────────────────────────

ACTIVE_COLORS = ["ivory", "blue", "red", "green", "black"]
JOKER_COLOR = "joker"  # white mottled
ALL_PIECE_COLORS = ACTIVE_COLORS + [JOKER_COLOR]

PIECES_PER_COLOR = 8  # 8 of each active color on the board
JOKER_COUNT = 3
TOTAL_ON_BOARD = PIECES_PER_COLOR * len(ACTIVE_COLORS) + JOKER_COUNT  # 43
MAX_STACK_HEIGHT = 5
MAX_CLAIMS_PER_PLAYER = 2

AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

# Color display info
COLOR_STYLES = {
    "ivory": {"hex": "#f5e6c8", "ref": "TZAAR"},
    "blue": {"hex": "#2980b9", "ref": "ZERTZ"},
    "red": {"hex": "#c0392b", "ref": "DVONN"},
    "green": {"hex": "#27ae60", "ref": "PUNCT"},
    "black": {"hex": "#2c3e50", "ref": "YINSH"},
    "joker": {"hex": "#ccc", "ref": "GIPF"},
}


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def is_valid(q, r):
    """Board: |q| <= 3, |r| <= 4, |q+r| <= 3. 43 positions."""
    return abs(q) <= 3 and abs(r) <= 4 and abs(q + r) <= 3


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "q,r" -> [] for all 43 positions (empty stacks)."""
    board = {}
    for q in range(-3, 4):
        for r in range(-4, 5):
            if is_valid(q, r):
                board[hex_key(q, r)] = []
    return board


def all_positions():
    return [(q, r) for q in range(-3, 4) for r in range(-4, 5) if is_valid(q, r)]


ALL_POSITIONS = all_positions()


def setup_random(board):
    """Place 43 pieces randomly: 8 of each active color + 3 jokers."""
    pieces = []
    for color in ACTIVE_COLORS:
        pieces.extend([color] * PIECES_PER_COLOR)
    pieces.extend([JOKER_COLOR] * JOKER_COUNT)
    random.shuffle(pieces)

    keys = list(board.keys())
    for i, key in enumerate(keys):
        board[key] = [pieces[i]]


# ── Movement helpers ──────────────────────────────────

def get_stack_top(stack):
    """Return the top color of a stack, or None if empty."""
    return stack[-1] if stack else None


def find_targets(board, from_key):
    """Find all positions reachable from from_key.

    A piece/stack can move to:
    - An adjacent occupied position
    - A position in a straight line across empty spaces (first occupied hit)

    Returns list of target keys.
    """
    q, r = parse_hex(from_key)
    targets = []

    for dq, dr in AXIAL_DIRS:
        nq, nr = q + dq, r + dr

        # Check adjacent first
        if is_valid(nq, nr):
            nk = hex_key(nq, nr)
            if nk in board and len(board[nk]) > 0:
                targets.append(nk)
                continue
            # Adjacent is empty — continue in this direction
            elif nk in board:
                nq += dq
                nr += dr
                while is_valid(nq, nr):
                    nk = hex_key(nq, nr)
                    if nk in board and len(board[nk]) > 0:
                        targets.append(nk)
                        break
                    elif nk not in board:
                        break
                    nq += dq
                    nr += dr

    return targets


def can_stack_on(from_stack, to_stack):
    """Check if from_stack can be placed on top of to_stack.

    Rules:
    - Combined height <= MAX_STACK_HEIGHT
    - All colors must be different (jokers are wildcards)
    """
    if len(from_stack) + len(to_stack) > MAX_STACK_HEIGHT:
        return False

    # Check color uniqueness: non-joker colors must all be different
    non_joker_colors = set()
    for color in from_stack + to_stack:
        if color != JOKER_COLOR:
            if color in non_joker_colors:
                return False
            non_joker_colors.add(color)

    return True


def can_move(from_stack, to_stack, from_top, player_claims, current_player_color):
    """Check if a move from from_stack to to_stack is valid considering movement restrictions.

    - Single neutral piece → can only land on single pieces
    - Stack with neutral top → can land on singles or equal/shorter stacks
    - Claimed color on top → can land on any piece/stack (subject to stacking rules)
    """
    from_top_color = from_top

    # Determine if the top color is claimed by current player
    is_claimed_by_me = from_top_color in player_claims.get(current_player_color, [])

    if is_claimed_by_me:
        # Claimed color on top — can land on anything (stacking rules apply separately)
        return True

    # Neutral or opponent's claimed color — restricted movement
    from_height = len(from_stack)

    if from_height == 1:
        # Single neutral piece — can only land on single pieces
        return len(to_stack) == 1
    else:
        # Stack with neutral top — can land on equal or shorter
        return len(to_stack) <= from_height


def is_moveable_by(stack, player_claims, current_player_color):
    """Check if a player can move this stack.

    - Joker alone: cannot be moved (passive)
    - Neutral color on top: either player can move
    - Player's claimed color on top: only that player
    - Opponent's claimed color on top: only opponent
    """
    if not stack:
        return False

    top = stack[-1]

    # Joker alone cannot be moved
    if top == JOKER_COLOR and len(stack) == 1:
        return False

    # Check if top color is claimed
    for player_color, claims in player_claims.items():
        if top in claims:
            return player_color == current_player_color

    # Unclaimed / joker on stack → either player can move
    return True


def find_valid_moves(board, player_claims, current_player_color):
    """Find all valid moves for the current player.

    Returns list of {"from": key, "to": key}.
    """
    moves = []

    for key, stack in board.items():
        if not stack:
            continue
        if not is_moveable_by(stack, player_claims, current_player_color):
            continue

        top = get_stack_top(stack)
        targets = find_targets(board, key)

        for tk in targets:
            to_stack = board[tk]
            if not can_stack_on(stack, to_stack):
                continue
            if not can_move(stack, to_stack, top, player_claims, current_player_color):
                continue
            moves.append({"from": key, "to": tk})

    return moves


def is_complete_stack(stack):
    """Check if this is a completed 5-stack."""
    return len(stack) >= MAX_STACK_HEIGHT


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    color = "white" if index == 0 else "black"  # player color (not piece color)
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
    }
