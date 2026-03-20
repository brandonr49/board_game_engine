"""YINSH board geometry, ring movement algorithm, and row detection."""

# ── Constants ─────────────────────────────────────────
RINGS_PER_PLAYER = 5
TOTAL_MARKERS = 51
ROW_LENGTH = 5

# Axial hex direction vectors
AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

# The 6 corner vertices of a radius-5 hexagon (excluded from the board)
_EXCLUDED_CORNERS = {(5, 0), (-5, 0), (0, 5), (0, -5), (5, -5), (-5, 5)}


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def is_valid(q, r):
    """Check if (q, r) is one of the 85 valid board positions."""
    if max(abs(q), abs(r), abs(q + r)) > 5:
        return False
    if (q, r) in _EXCLUDED_CORNERS:
        return False
    return True


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "q,r" -> None for all 85 valid positions.
    None means empty; will be set to {"type": "ring"|"marker", "color": ...}."""
    board = {}
    for q in range(-5, 6):
        for r in range(-5, 6):
            if is_valid(q, r):
                board[hex_key(q, r)] = None
    return board


def all_positions():
    """Return list of all valid (q, r) tuples."""
    positions = []
    for q in range(-5, 6):
        for r in range(-5, 6):
            if is_valid(q, r):
                positions.append((q, r))
    return positions


ALL_POSITIONS = all_positions()


# ── Ring movement ─────────────────────────────────────

def find_ring_moves(board, from_key):
    """
    Compute all valid destinations for a ring at from_key.

    Returns list of {"to": key, "flipped": [key, ...]} dicts.

    Movement rules:
    - Move in a straight line along one of 6 directions
    - Can traverse empty spaces (each is a valid destination)
    - When hitting consecutive markers, jump over ALL of them
    - Land on the first empty space after the markers
    - Jumped markers get flipped
    - Cannot move through empty spaces AFTER a jump
    - Cannot jump over rings
    """
    q, r = parse_hex(from_key)
    moves = []

    for dq, dr in AXIAL_DIRS:
        cq, cr = q + dq, r + dr
        jumped_markers = []
        jumping = False

        while is_valid(cq, cr):
            key = hex_key(cq, cr)
            cell = board.get(key)

            if cell is None:
                # Empty space
                if jumping:
                    # Landing after a jump — valid destination, then stop
                    moves.append({"to": key, "flipped": list(jumped_markers)})
                    break
                else:
                    # Moving through empty spaces — valid destination, continue
                    moves.append({"to": key, "flipped": []})
            elif cell["type"] == "marker":
                # Marker — start or continue jumping
                jumping = True
                jumped_markers.append(key)
            elif cell["type"] == "ring":
                # Ring — blocked, stop
                break

            cq += dq
            cr += dr

    return moves


# ── Row detection ─────────────────────────────────────

def find_rows(board, color):
    """
    Find all rows of exactly ROW_LENGTH same-color markers in straight lines.

    Returns list of rows, where each row is a list of ROW_LENGTH hex_key strings.
    A row of 6+ will yield multiple overlapping rows of 5.
    """
    rows = []

    # Only need to check 3 directions (the other 3 are reverse)
    check_dirs = [(1, 0), (0, 1), (1, -1)]

    # For each direction, scan all lines through the board
    for dq, dr in check_dirs:
        # Collect all lines: group positions by their perpendicular coordinate
        lines = {}
        for q, r in ALL_POSITIONS:
            # Project onto the perpendicular axis to group into lines
            # For direction (1,0): lines share the same r
            # For direction (0,1): lines share the same q
            # For direction (1,-1): lines share the same q+r
            if (dq, dr) == (1, 0):
                line_id = r
            elif (dq, dr) == (0, 1):
                line_id = q
            else:  # (1, -1)
                line_id = q + r

            if line_id not in lines:
                lines[line_id] = []
            lines[line_id].append((q, r))

        # Sort each line's points along the direction
        for line_id, points in lines.items():
            if (dq, dr) == (1, 0):
                points.sort(key=lambda p: p[0])
            elif (dq, dr) == (0, 1):
                points.sort(key=lambda p: p[1])
            else:
                points.sort(key=lambda p: p[0])

            # Scan for consecutive runs of the target color
            run = []
            for pq, pr in points:
                key = hex_key(pq, pr)
                cell = board.get(key)
                if cell and cell["type"] == "marker" and cell["color"] == color:
                    run.append(key)
                else:
                    # Emit all windows of ROW_LENGTH from this run
                    if len(run) >= ROW_LENGTH:
                        for i in range(len(run) - ROW_LENGTH + 1):
                            rows.append(run[i:i + ROW_LENGTH])
                    run = []

            # Don't forget the last run
            if len(run) >= ROW_LENGTH:
                for i in range(len(run) - ROW_LENGTH + 1):
                    rows.append(run[i:i + ROW_LENGTH])

    return rows


def rows_are_intersecting(row_a, row_b):
    """Check if two rows share any marker positions."""
    return bool(set(row_a) & set(row_b))


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    color = "white" if index == 0 else "black"
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
        "rings_on_board": 0,
        "rings_removed": 0,
    }
