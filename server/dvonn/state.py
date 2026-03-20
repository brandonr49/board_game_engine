"""DVONN board geometry, neighbor math, movement helpers, and connectivity."""

# ── Constants ─────────────────────────────────────────
ROW_SIZES = [9, 10, 11, 10, 9]
TOTAL_SPACES = 49  # sum(ROW_SIZES)
PIECES_PER_PLAYER = 23
DVONN_PIECE_COUNT = 3

# Column offsets: rows 0,1,2 start at col 0; rows 3,4 are shifted right by 1
COL_OFFSETS = [0, 0, 0, 1, 1]


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
# The board uses an offset hex grid (pointy-top orientation).
# Rows 0,1,2 have offset 0; rows 3,4 have offset 1.
# For adjacency, we convert to axial coordinates:
#   axial_q = col - offset
#   axial_r = row
# Axial neighbors of (q, r): (q+1,r), (q-1,r), (q,r+1), (q,r-1), (q+1,r-1), (q-1,r+1)

def _to_axial(row, col):
    return col - COL_OFFSETS[row], row


def _from_axial(q, r):
    if r < 0 or r >= len(ROW_SIZES):
        return None
    col = q + COL_OFFSETS[r]
    if not is_valid_position(r, col):
        return None
    return r, col


_AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


def get_neighbors(row, col):
    """Return list of valid (row, col) neighbors on the board."""
    q, r = _to_axial(row, col)
    result = []
    for dq, dr in _AXIAL_DIRS:
        pos = _from_axial(q + dq, r + dr)
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

    q, r = _to_axial(row, col)
    destinations = []

    for dq, dr in _AXIAL_DIRS:
        tq, tr = q + dq * stack_height, r + dr * stack_height
        pos = _from_axial(tq, tr)
        if pos is None:
            continue
        dest_key = board_key(pos[0], pos[1])
        if dest_key in board and len(board[dest_key]["stack"]) > 0:
            destinations.append(pos)

    return destinations


def is_straight_line(from_row, from_col, to_row, to_col, distance):
    """Check if (from) to (to) is a straight axial line of given distance."""
    fq, fr = _to_axial(from_row, from_col)
    tq, tr = _to_axial(to_row, to_col)
    dq, dr = tq - fq, tr - fr

    for dirq, dirr in _AXIAL_DIRS:
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
