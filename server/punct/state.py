"""PUNCT board geometry, piece shapes, rotation, stacking, bridging, connection detection."""

# ── Constants ─────────────────────────────────────────

BOARD_RADIUS = 8
CENTRAL_RADIUS = 2
AXIAL_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

_EXCLUDED_CORNERS = {(8, 0), (-8, 0), (0, 8), (0, -8), (8, -8), (-8, 8)}

SHAPES = ["straight", "angular", "triangular"]
PIECES_PER_SHAPE = 6

# ── Piece rotations ──────────────────────────────────
# Each rotation is a tuple of 2 (dq, dr) offsets for the minor dots,
# relative to PUNCT at (0, 0).

STRAIGHT_ROTATIONS = [
    ((1, 0), (-1, 0)),
    ((0, 1), (0, -1)),
    ((1, -1), (-1, 1)),
]

ANGULAR_ROTATIONS = [
    ((1, 0), (0, 1)),
    ((0, 1), (-1, 1)),
    ((-1, 1), (-1, 0)),
    ((-1, 0), (0, -1)),
    ((0, -1), (1, -1)),
    ((1, -1), (1, 0)),
]

TRIANGULAR_ROTATIONS = [
    ((1, 0), (1, -1)),
    ((1, 0), (0, 1)),
    ((0, 1), (-1, 1)),
    ((-1, 0), (-1, 1)),
    ((-1, 0), (0, -1)),
    ((0, -1), (1, -1)),
]

ROTATIONS = {
    "straight": STRAIGHT_ROTATIONS,
    "angular": ANGULAR_ROTATIONS,
    "triangular": TRIANGULAR_ROTATIONS,
}


# ── Coordinate helpers ────────────────────────────────

def hex_key(q, r):
    return f"{q},{r}"


def parse_hex(key):
    parts = key.split(",")
    return int(parts[0]), int(parts[1])


def hex_distance(q, r):
    return max(abs(q), abs(r), abs(q + r))


def is_valid(q, r):
    """On the 211-space board."""
    if hex_distance(q, r) > BOARD_RADIUS:
        return False
    return (q, r) not in _EXCLUDED_CORNERS


def is_central(q, r):
    """In the central hexagon (radius 2 = 19 spaces)."""
    return hex_distance(q, r) <= CENTRAL_RADIUS


# ── Board generation ──────────────────────────────────

def generate_positions():
    """Return set of all 211 valid hex_key strings."""
    positions = set()
    for q in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
        for r in range(-BOARD_RADIUS, BOARD_RADIUS + 1):
            if is_valid(q, r):
                positions.add(hex_key(q, r))
    return positions


ALL_POSITIONS = generate_positions()


# ── Board sides (for connection) ─────────────────────
# 3 pairs of opposite sides. Each side is a set of edge positions.
# The hex has 6 edges. Opposite edges form connection targets.

def _compute_sides():
    """Compute the 3 pairs of opposite board sides.

    In axial coords for a hex of radius 8, the 6 sides are groups of
    border positions. Two positions are on the same side if they share
    the same boundary constraint.

    Side definitions (by which cube coordinate is at extreme):
    - Side A: q = 8 (right)      ↔ Side D: q = -8 (left)
    - Side B: r = 8 (bottom-right) ↔ Side E: r = -8 (top-left)
    - Side C: q+r = 8 (bottom)   ↔ Side F: q+r = -8 (top)

    But we exclude corners, so each side has positions along the edge
    minus the corner vertices.
    """
    sides = {
        "A": set(), "B": set(), "C": set(),
        "D": set(), "E": set(), "F": set(),
    }

    for key in ALL_POSITIONS:
        q, r = parse_hex(key)
        d = hex_distance(q, r)
        if d != BOARD_RADIUS:
            continue
        # This is a border position — determine which side
        s = q + r
        if q == BOARD_RADIUS:
            sides["A"].add(key)
        elif q == -BOARD_RADIUS:
            sides["D"].add(key)
        elif r == BOARD_RADIUS:
            sides["B"].add(key)
        elif r == -BOARD_RADIUS:
            sides["E"].add(key)
        elif s == BOARD_RADIUS:
            sides["C"].add(key)
        elif s == -BOARD_RADIUS:
            sides["F"].add(key)

    # 3 pairs of opposite sides
    return [
        (sides["A"], sides["D"]),
        (sides["B"], sides["E"]),
        (sides["C"], sides["F"]),
    ]


SIDE_PAIRS = _compute_sides()


# ── Piece helpers ─────────────────────────────────────

def compute_piece_cells(punct_q, punct_r, shape, rotation_idx):
    """Compute the 3 cell positions for a piece.
    Returns (punct_key, minor1_key, minor2_key) or None if any cell off-board.
    """
    rotations = ROTATIONS[shape]
    if rotation_idx < 0 or rotation_idx >= len(rotations):
        return None

    d1, d2 = rotations[rotation_idx]
    m1q, m1r = punct_q + d1[0], punct_r + d1[1]
    m2q, m2r = punct_q + d2[0], punct_r + d2[1]

    pk = hex_key(punct_q, punct_r)
    m1k = hex_key(m1q, m1r)
    m2k = hex_key(m2q, m2r)

    if pk not in ALL_POSITIONS or m1k not in ALL_POSITIONS or m2k not in ALL_POSITIONS:
        return None

    return (pk, m1k, m2k)


def create_piece(piece_id, color, shape, punct_key, minor_keys, level=1):
    return {
        "id": piece_id,
        "color": color,
        "shape": shape,
        "punct_pos": punct_key,
        "minor_positions": list(minor_keys),
        "level": level,
    }


def get_piece_cells(piece):
    """Return all 3 cell keys for a piece."""
    return [piece["punct_pos"]] + piece["minor_positions"]


# ── Grid / visibility ────────────────────────────────

def build_grid(pieces):
    """Build a grid mapping: {cell_key: [(piece_id, level), ...]} sorted by level."""
    grid = {}
    for pid, piece in pieces.items():
        level = piece["level"]
        for cell_key in get_piece_cells(piece):
            if cell_key not in grid:
                grid[cell_key] = []
            grid[cell_key].append((pid, level))

    # Sort each cell's entries by level
    for key in grid:
        grid[key].sort(key=lambda x: x[1])

    return grid


def get_top_piece_at(grid, pieces, cell_key):
    """Return the piece_id of the topmost piece at a cell, or None."""
    if cell_key not in grid or not grid[cell_key]:
        return None
    return grid[cell_key][-1][0]  # highest level


def get_visible_dots(pieces):
    """Return dict of {cell_key: color} for all dots visible from above."""
    grid = build_grid(pieces)
    visible = {}
    for cell_key, entries in grid.items():
        if entries:
            top_pid = entries[-1][0]
            visible[cell_key] = pieces[top_pid]["color"]
    return visible


def is_piece_blocked(pieces, piece_id):
    """A piece is blocked if any of its dots is covered by another piece."""
    grid = build_grid(pieces)
    piece = pieces[piece_id]
    for cell_key in get_piece_cells(piece):
        entries = grid.get(cell_key, [])
        # Check if anything is on top of this piece at this cell
        for pid, level in entries:
            if pid != piece_id and level > piece["level"]:
                return True
    return False


# ── Movement validation ──────────────────────────────

def is_straight_line(q1, r1, q2, r2):
    """Check if two positions are on a straight axial line and return direction, or None."""
    dq = q2 - q1
    dr = r2 - r1

    if dq == 0 and dr == 0:
        return None

    for dirq, dirr in AXIAL_DIRS:
        if dirq == 0 and dirr == 0:
            continue
        # Check if (dq, dr) is a positive multiple of (dirq, dirr)
        if dirq != 0:
            t = dq / dirq
        elif dirr != 0:
            t = dr / dirr
        else:
            continue

        if t > 0 and t == int(t):
            if dq == dirq * int(t) and dr == dirr * int(t):
                return (dirq, dirr)

    return None


# ── Bridge detection ─────────────────────────────────

def is_bridge_placement(shape, cells, pieces, grid):
    """Check if this placement forms a valid bridge.

    A bridge occurs when:
    - Shape is straight or angular (NOT triangular)
    - Two of the three dots rest on pieces at the same level
    - The third dot (middle for straight, or the PUNCT for angular) is unsupported

    For simplicity: a bridge is when exactly 2 of the 3 cells have support
    and 1 cell has no support at the required level.
    """
    if shape == "triangular":
        return False

    # Check how many cells have support
    supported = []
    unsupported = []

    for cell_key in cells:
        entries = grid.get(cell_key, [])
        if entries:
            supported.append(cell_key)
        else:
            unsupported.append(cell_key)

    # Bridge: exactly 1 unsupported cell, 2 supported cells at same level
    if len(unsupported) != 1 or len(supported) != 2:
        return False

    # Check the 2 supported cells are at the same level
    level1 = grid[supported[0]][-1][1] if grid[supported[0]] else 0
    level2 = grid[supported[1]][-1][1] if grid[supported[1]] else 0

    return level1 == level2


# ── Connection detection ─────────────────────────────

def check_connection(pieces, color):
    """Check if 'color' has connected any pair of opposite sides.
    Returns True if visible dots form a path between opposite sides.
    """
    visible = get_visible_dots(pieces)

    # Get all cells with visible dots of this color
    color_cells = {key for key, c in visible.items() if c == color}
    if not color_cells:
        return False

    for side_a, side_b in SIDE_PAIRS:
        # Check if any color_cell touches side_a and any touches side_b
        starts = color_cells & side_a
        if not starts:
            continue

        # BFS from starts to see if we reach side_b
        visited = set(starts)
        queue = list(starts)
        while queue:
            current = queue.pop(0)
            if current in side_b:
                return True
            cq, cr = parse_hex(current)
            for dq, dr in AXIAL_DIRS:
                nk = hex_key(cq + dq, cr + dr)
                if nk in color_cells and nk not in visited:
                    visited.add(nk)
                    queue.append(nk)

    return False


def count_central_dots(pieces, color):
    """Count visible dots of 'color' in the central hexagon."""
    visible = get_visible_dots(pieces)
    count = 0
    for key, c in visible.items():
        if c == color:
            q, r = parse_hex(key)
            if is_central(q, r):
                count += 1
    return count


# ── Reserve generation ────────────────────────────────

def generate_reserve(color):
    """Generate list of piece IDs for a player's 18 pieces."""
    prefix = "w" if color == "white" else "b"
    reserve = []
    for shape in SHAPES:
        for i in range(PIECES_PER_SHAPE):
            reserve.append(f"{prefix}_{shape}_{i}")
    return reserve


def get_piece_shape_from_id(piece_id):
    """Extract shape from piece ID like 'w_straight_0'."""
    parts = piece_id.split("_")
    return parts[1]


def get_piece_color_from_id(piece_id):
    """Extract color from piece ID."""
    return "white" if piece_id.startswith("w_") else "black"


# ── Player creation ───────────────────────────────────

def create_player(index, player_id, name):
    color = "white" if index == 0 else "black"
    return {
        "index": index,
        "player_id": player_id,
        "name": name,
        "color": color,
    }
