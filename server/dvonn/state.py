"""DVONN board geometry, neighbor math, movement helpers, and connectivity."""

# ── Constants ─────────────────────────────────────────
ROW_SIZES = [9, 10, 11, 10, 9]
TOTAL_SPACES = 49  # sum(ROW_SIZES)
PIECES_PER_PLAYER = 23
DVONN_PIECE_COUNT = 3

# All rows start at col 0; the diamond shape comes from visual indentation
COL_OFFSETS = [0, 0, 0, 0, 0]

# Half-hex-width indentation per row (symmetric diamond)
ROW_INDENT = [2, 1, 0, 1, 2]


# ── Coordinate helpers ────────────────────────────────

def board_key(row, col):
    return f"{row},{col}"


def parse_key(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def is_valid_position(row, col):
    if row < 0 or row >= len(ROW_SIZES):
        return False
    offset = COL_OFFSETS[row]
    return offset <= col < offset + ROW_SIZES[row]


# ── Cube coordinate conversion ───────────────────────
# We use cube coordinates (q, r, s where q+r+s=0) for hex math.
# The conversion accounts for the diamond layout indentation.

def _to_cube(row, col):
    """Convert offset (row, col) to cube coordinates (q, r)."""
    q = (ROW_INDENT[row] + col * 2 - row) // 2
    r = row
    return q, r


def _from_cube(q, r):
    """Convert cube (q, r) back to offset (row, col). Returns None if invalid."""
    if r < 0 or r >= len(ROW_SIZES):
        return None
    col = (2 * q - ROW_INDENT[r] + r) // 2
    # Verify the conversion is exact (no rounding errors)
    check_val = ROW_INDENT[r] + col * 2 - r
    if check_val != 2 * q:
        return None
    if not is_valid_position(r, col):
        return None
    return r, col


# 6 cube directions: (dq, dr) pairs (ds = -dq - dr is implicit)
_CUBE_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "row,col" -> {"stack": [], "row": int, "col": int}."""
    board = {}
    for row, size in enumerate(ROW_SIZES):
        offset = COL_OFFSETS[row]
        for col in range(offset, offset + size):
            board[board_key(row, col)] = {
                "stack": [],
                "row": row,
                "col": col,
            }
    return board


# ── Neighbor calculation ──────────────────────────────

def get_neighbors(row, col):
    """Return list of valid (row, col) neighbors on the board."""
    q, r = _to_cube(row, col)
    result = []
    for dq, dr in _CUBE_DIRS:
        pos = _from_cube(q + dq, r + dr)
        if pos is not None:
            result.append(pos)
    return result


# ── Line movement ─────────────────────────────────────

def get_line_destinations(board, row, col, stack_height):
    """
    Return list of (dest_row, dest_col) reachable by moving exactly
    stack_height steps in a straight line from (row, col).
    Must land on an occupied space (non-empty stack). Can jump over empties.
    """
    if stack_height < 1:
        return []

    q, r = _to_cube(row, col)
    destinations = []

    for dq, dr in _CUBE_DIRS:
        tq, tr = q + dq * stack_height, r + dr * stack_height
        pos = _from_cube(tq, tr)
        if pos is None:
            continue
        dest_key = board_key(pos[0], pos[1])
        if dest_key in board and len(board[dest_key]["stack"]) > 0:
            destinations.append(pos)

    return destinations


def is_straight_line(from_row, from_col, to_row, to_col, distance):
    """Check if (from) to (to) is a straight cube-coordinate line of given distance."""
    fq, fr = _to_cube(from_row, from_col)
    tq, tr = _to_cube(to_row, to_col)
    dq, dr = tq - fq, tr - fr

    for dirq, dirr in _CUBE_DIRS:
        if dq == dirq * distance and dr == dirr * distance:
            return True
    return False


# ── Surrounded check ──────────────────────────────────

def is_surrounded(board, row, col):
    """A piece/stack is surrounded if ALL 6 neighbors are occupied."""
    neighbors = get_neighbors(row, col)
    if len(neighbors) < 6:
        # Edge/corner pieces have fewer than 6 neighbors — not fully surrounded
        return False
    for nr, nc in neighbors:
        key = board_key(nr, nc)
        if key not in board or len(board[key]["stack"]) == 0:
            return False
    return True


# ── Connectivity (flood fill from DVONN pieces) ──────

def find_connected_to_dvonn(board):
    """
    Return set of board_key strings that are connected (via chain of
    occupied neighbors) to at least one stack containing a DVONN piece.
    """
    # Find all positions containing at least one "dvonn" piece
    dvonn_positions = []
    for key, space in board.items():
        if any(piece == "dvonn" for piece in space["stack"]):
            dvonn_positions.append(key)

    # BFS from all DVONN positions
    visited = set()
    queue = list(dvonn_positions)
    visited.update(queue)

    while queue:
        current = queue.pop(0)
        row, col = parse_key(current)
        for nr, nc in get_neighbors(row, col):
            nkey = board_key(nr, nc)
            if nkey in visited:
                continue
            if nkey in board and len(board[nkey]["stack"]) > 0:
                visited.add(nkey)
                queue.append(nkey)

    return visited


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    color = "white" if index == 0 else "black"
    dvonn_to_place = 2 if index == 0 else 1
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
        "pieces_to_place": PIECES_PER_PLAYER,
        "dvonn_to_place": dvonn_to_place,
    }
