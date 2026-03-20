"""ZERTZ board geometry, capture algorithm, free ring detection, connectivity."""

# ── Constants ─────────────────────────────────────────

POOL_NORMAL = {"white": 6, "gray": 8, "black": 10}
POOL_BLITZ = {"white": 5, "gray": 7, "black": 9}

WIN_NORMAL = {"each": 3, "white": 4, "gray": 5, "black": 6}
WIN_BLITZ = {"each": 2, "white": 3, "gray": 4, "black": 5}

MARBLE_COLORS = ["white", "gray", "black"]

AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

BOARD_RADIUS = 3


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def is_valid(q, r):
    """Check if (q, r) is on the initial radius-3 hex board (37 positions)."""
    return max(abs(q), abs(r), abs(q + r)) <= BOARD_RADIUS


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "q,r" -> None for all 37 positions. None = vacant ring."""
    board = {}
    for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
        for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            if is_valid(q, r):
                board[hex_key(q, r)] = None
    return board


# ── Neighbor helpers ──────────────────────────────────

def get_neighbors_on_board(board, q, r):
    """Return list of (q, r) neighbors that still exist in the board."""
    result = []
    for dq, dr in AXIAL_DIRS:
        nq, nr = q + dq, r + dr
        if hex_key(nq, nr) in board:
            result.append((nq, nr))
    return result


def is_edge_ring(board, q, r):
    """A ring is on the edge if it has fewer than 6 neighbors in the board."""
    count = 0
    for dq, dr in AXIAL_DIRS:
        if hex_key(q + dq, r + dr) in board:
            count += 1
    return count < 6


# ── Connectivity check ───────────────────────────────

def board_stays_connected(board, remove_key):
    """Check if removing remove_key would keep all remaining rings connected."""
    remaining = set(board.keys()) - {remove_key}
    if len(remaining) <= 1:
        return True

    # BFS from any remaining ring
    start = next(iter(remaining))
    visited = {start}
    queue = [start]

    while queue:
        current = queue.pop(0)
        cq, cr = parse_hex(current)
        for dq, dr in AXIAL_DIRS:
            nkey = hex_key(cq + dq, cr + dr)
            if nkey in remaining and nkey not in visited:
                visited.add(nkey)
                queue.append(nkey)

    return len(visited) == len(remaining)


# ── Free ring detection ──────────────────────────────

def find_free_rings(board):
    """Find all rings that are vacant, on the edge, and removable without disconnecting."""
    free = []
    for key, marble in board.items():
        if marble is not None:
            continue  # occupied
        q, r = parse_hex(key)
        if not is_edge_ring(board, q, r):
            continue  # not on edge
        if not board_stays_connected(board, key):
            continue  # would disconnect
        free.append(key)
    return free


# ── Capture detection ─────────────────────────────────

def find_single_jumps(board, from_key):
    """Find all immediate single jumps from a marble at from_key.
    Returns list of {"to": key, "captured": key, "direction": (dq,dr)}."""
    q, r = parse_hex(from_key)
    jumps = []

    for dq, dr in AXIAL_DIRS:
        mid_q, mid_r = q + dq, r + dr
        mid_key = hex_key(mid_q, mid_r)
        land_q, land_r = q + 2 * dq, r + 2 * dr
        land_key = hex_key(land_q, land_r)

        # Mid must exist and have a marble
        if mid_key not in board or board[mid_key] is None:
            continue
        # Landing must exist and be vacant
        if land_key not in board or board[land_key] is not None:
            continue

        jumps.append({
            "to": land_key,
            "captured": mid_key,
        })

    return jumps


def find_capture_sequences(board, from_key):
    """Find all possible capture sequences (including multi-jumps) from from_key.

    Returns list of sequences, where each sequence is a list of
    {"from": key, "to": key, "captured": key} steps.

    Multi-jumps are mandatory if available, so only maximal sequences are returned.
    """
    marble_color = board.get(from_key)
    if marble_color is None:
        return []

    results = []

    def _recurse(current_key, board_state, path):
        jumps = find_single_jumps(board_state, current_key)
        if not jumps:
            # No more jumps — this is a complete sequence
            if path:
                results.append(list(path))
            return

        for jump in jumps:
            # Simulate the jump
            new_board = dict(board_state)
            new_board[jump["to"]] = new_board[current_key]
            new_board[current_key] = None
            new_board[jump["captured"]] = None

            step = {
                "from": current_key,
                "to": jump["to"],
                "captured": jump["captured"],
            }
            path.append(step)
            _recurse(jump["to"], new_board, path)
            path.pop()

    _recurse(from_key, board, [])
    return results


def find_all_captures(board):
    """Find all possible capture sequences for any marble on the board.
    Returns list of {"start": key, "sequence": [...]} dicts."""
    all_captures = []

    for key, marble in board.items():
        if marble is None:
            continue
        sequences = find_capture_sequences(board, key)
        for seq in sequences:
            all_captures.append({"start": key, "sequence": seq})

    return all_captures


def has_any_capture(board):
    """Quick check: is there any capture possible?"""
    for key, marble in board.items():
        if marble is None:
            continue
        jumps = find_single_jumps(board, key)
        if jumps:
            return True
    return False


# ── Isolated group detection ─────────────────────────

def find_isolated_marbles(board):
    """After a board change, find groups of rings disconnected from the main board.
    Returns list of (key, marble_color) for marbles on isolated rings."""
    if not board:
        return []

    # Find the largest connected component
    all_keys = set(board.keys())
    if not all_keys:
        return []

    # BFS from the first key to find the main component
    start = next(iter(all_keys))
    visited = {start}
    queue = [start]
    while queue:
        current = queue.pop(0)
        cq, cr = parse_hex(current)
        for dq, dr in AXIAL_DIRS:
            nkey = hex_key(cq + dq, cr + dr)
            if nkey in all_keys and nkey not in visited:
                visited.add(nkey)
                queue.append(nkey)

    # Anything not visited is isolated
    isolated_marbles = []
    isolated_keys = all_keys - visited
    for key in isolated_keys:
        if board[key] is not None:
            isolated_marbles.append((key, board[key]))

    return isolated_marbles


# ── Win condition check ──────────────────────────────

def check_win(captured, win_conditions):
    """Check if captured marbles meet any win condition.
    captured: {"white": int, "gray": int, "black": int}
    win_conditions: {"each": int, "white": int, "gray": int, "black": int}
    """
    # Check "each" condition (N of each color)
    each = win_conditions["each"]
    if all(captured[c] >= each for c in MARBLE_COLORS):
        return True

    # Check individual color conditions
    for color in MARBLE_COLORS:
        if captured[color] >= win_conditions[color]:
            return True

    return False


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "captured": {"white": 0, "gray": 0, "black": 0},
    }
