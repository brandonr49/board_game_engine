"""GIPF board geometry, edge dots, push mechanics, and row detection."""

# ── Constants ─────────────────────────────────────────

BOARD_RADIUS = 3
AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

# Starting corner spots (the 6 vertices of the radius-3 hex, one step inside)
# These are at distance 2 from center, positioned toward each corner
CORNER_SPOTS_WHITE = ["1,-2", "-1,-1", "-2,1"]  # alternating
CORNER_SPOTS_BLACK = ["2,-1", "0,-2", "-1,2"]   # wait, let me compute properly

# The 6 corner directions of a hex board
# At radius 3, the corners are at (3,0), (0,3), (-3,3), (-3,0), (0,-3), (3,-3)
# The "angular dots" are one step further at radius 4
# The first spots toward center from those angular dots are at radius 2
# Actually the corners of the board (distance 3) are: (3,0), (-3,0), (0,3), (0,-3), (3,-3), (-3,3)
# The initial pieces go on these spots. White and black alternate.
INITIAL_CORNERS = [
    (3, -3), (0, 3), (-3, 0),   # one set
    (3, 0), (-3, 3), (0, -3),   # other set
]
# First 3 = white, next 3 = black (alternating around the hex)


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def hex_distance(q, r):
    return max(abs(q), abs(r), abs(q + r))


def is_board_spot(q, r):
    """On the 37-spot hex board (radius 3)."""
    return hex_distance(q, r) <= BOARD_RADIUS


# ── Board generation ──────────────────────────────────

def generate_board():
    """Return dict of "q,r" -> None for all 37 spots."""
    board = {}
    for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
        for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            if is_board_spot(q, r):
                board[hex_key(q, r)] = None
    return board


# ── Edge dots ─────────────────────────────────────────

def generate_edge_dots():
    """Generate the 24 edge entry dots.

    Each dot is one step outside the board from a border spot.
    Returns list of {"dot_key": str, "direction": (dq,dr), "first_spot_key": str}.
    The direction points FROM the dot INTO the board.
    """
    dots = []
    seen_dots = set()

    for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
        for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            if not is_board_spot(q, r):
                continue
            # This is a board spot. Check each direction for going off-board.
            for dq, dr in AXIAL_DIRS:
                oq, orr = q + dq, r + dr
                if not is_board_spot(oq, orr):
                    # (oq, orr) is off the board — it's a potential edge dot
                    dot_key = hex_key(oq, orr)
                    if dot_key not in seen_dots:
                        seen_dots.add(dot_key)
                        # Direction from dot into board = (-dq, -dr)
                        # First spot = (q, r)
                        dots.append({
                            "dot_key": dot_key,
                            "direction": (-dq, -dr),
                            "first_spot_key": hex_key(q, r),
                        })

    return dots


EDGE_DOTS = generate_edge_dots()
EDGE_DOT_MAP = {d["dot_key"]: d for d in EDGE_DOTS}


# ── Push mechanics ────────────────────────────────────

def can_push(board, dot_info):
    """Check if we can push from this edge dot (line not completely full)."""
    dq, dr = dot_info["direction"]
    q, r = parse_hex(dot_info["first_spot_key"])

    # Walk along the line until we find an empty spot or go off the board
    while is_board_spot(q, r):
        key = hex_key(q, r)
        if board.get(key) is None:
            return True  # Found an empty spot — room to push
        q += dq
        r += dr

    return False  # Line is full — cannot push


def execute_push(board, dot_info, piece):
    """Push a piece from an edge dot into the board.

    piece: {"color": str, "is_gipf": bool}
    Mutates board in place.
    """
    dq, dr = dot_info["direction"]
    fq, fr = parse_hex(dot_info["first_spot_key"])

    # Collect all spots on this line (from first_spot in direction until off-board)
    line = []
    q, r = fq, fr
    while is_board_spot(q, r):
        line.append(hex_key(q, r))
        q += dq
        r += dr

    # Find the first empty spot in the line
    first_empty = None
    for i, key in enumerate(line):
        if board[key] is None:
            first_empty = i
            break

    if first_empty is None:
        raise ValueError("Line is full — cannot push")

    # Shift pieces from first_empty back to position 0
    # Move each piece one step deeper: line[i] = line[i-1], ..., line[1] = line[0]
    for i in range(first_empty, 0, -1):
        board[line[i]] = board[line[i - 1]]

    # Place new piece at first spot
    board[line[0]] = piece


# ── Row detection ─────────────────────────────────────

def find_rows_of_four(board, color):
    """Find all rows of 4+ same-color pieces in a line.

    Returns list of rows. Each row is a dict:
    {"keys": [all keys in the row including extensions],
     "core_keys": [the 4+ same-color keys],
     "extension_keys": [keys extending beyond the core]}

    A row includes the 4+ core same-color pieces plus any direct extensions
    (pieces of any color that continue the line beyond the core).
    """
    rows = []
    check_dirs = [(1, 0), (0, 1), (1, -1)]  # 3 directions (avoid reverse duplicates)

    for dq, dr in check_dirs:
        # Group positions into lines by their perpendicular coordinate
        lines = {}
        for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
                if not is_board_spot(q, r):
                    continue
                if (dq, dr) == (1, 0):
                    line_id = r
                elif (dq, dr) == (0, 1):
                    line_id = q
                else:
                    line_id = q + r
                if line_id not in lines:
                    lines[line_id] = []
                lines[line_id].append((q, r))

        for line_id, points in lines.items():
            # Sort along the direction
            if (dq, dr) == (1, 0):
                points.sort(key=lambda p: p[0])
            elif (dq, dr) == (0, 1):
                points.sort(key=lambda p: p[1])
            else:
                points.sort(key=lambda p: p[0])

            # Find runs of 4+ same-color pieces
            # We need contiguous runs (no gaps — all spots must be occupied)
            i = 0
            while i < len(points):
                q, r = points[i]
                key = hex_key(q, r)
                piece = board.get(key)

                if piece is not None and piece["color"] == color:
                    # Start a run
                    run_start = i
                    run_end = i
                    while run_end + 1 < len(points):
                        nq, nr = points[run_end + 1]
                        nkey = hex_key(nq, nr)
                        npiece = board.get(nkey)
                        if npiece is not None and npiece["color"] == color:
                            run_end += 1
                        else:
                            break

                    run_len = run_end - run_start + 1
                    if run_len >= 4:
                        # Found a row! Now find extensions
                        core_keys = [hex_key(*points[j]) for j in range(run_start, run_end + 1)]

                        # Extend backward
                        ext_keys = []
                        j = run_start - 1
                        while j >= 0:
                            ek = hex_key(*points[j])
                            if board.get(ek) is not None:
                                ext_keys.append(ek)
                                j -= 1
                            else:
                                break

                        # Extend forward
                        j = run_end + 1
                        while j < len(points):
                            ek = hex_key(*points[j])
                            if board.get(ek) is not None:
                                ext_keys.append(ek)
                                j += 1
                            else:
                                break

                        rows.append({
                            "keys": core_keys + ext_keys,
                            "core_keys": core_keys,
                            "extension_keys": ext_keys,
                        })

                    i = run_end + 1
                else:
                    i += 1

    return rows


# ── Setup helpers ─────────────────────────────────────

def setup_basic(board):
    """Place 3 white and 3 black single pieces at corner spots."""
    # The 6 corners of a radius-3 hex
    corners = [(3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3)]
    colors = ["white", "black", "white", "black", "white", "black"]
    for (q, r), color in zip(corners, colors):
        board[hex_key(q, r)] = {"color": color, "is_gipf": False}


def setup_standard(board):
    """Place 3 white and 3 black GIPF-pieces at corner spots."""
    corners = [(3, 0), (0, 3), (-3, 3), (-3, 0), (0, -3), (3, -3)]
    colors = ["white", "black", "white", "black", "white", "black"]
    for (q, r), color in zip(corners, colors):
        board[hex_key(q, r)] = {"color": color, "is_gipf": True}


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name, reserve_count):
    color = "white" if index == 0 else "black"
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
        "reserve": reserve_count,
        "captured_opponent": 0,
        "has_played_single": False,
    }
