"""PUNCT game engine — GameEngine subclass with Basic and Standard modes."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.punct.state import (
    SHAPES, ROTATIONS, ALL_POSITIONS,
    hex_key, parse_hex, is_valid, is_central,
    compute_piece_cells, create_piece, get_piece_cells,
    build_grid, get_top_piece_at, is_piece_blocked,
    is_straight_line, is_bridge_placement,
    check_connection, count_central_dots,
    generate_reserve, get_piece_shape_from_id, get_piece_color_from_id,
    create_player,
)


class PunctEngine(GameEngine):
    player_count_range = (2, 2)

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "punct",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "pieces": {},
            "reserve": {
                "white": generate_reserve("white"),
                "black": generate_reserve("black"),
            },
            "current_player": 0,
            "mode": "basic",
            "phase": "config",
            "sub_phase": None,
            "is_first_move": True,
            "game_over": False,
            "winner": None,
        }

    def get_player_view(self, state, player_id):
        view = deepcopy(state)
        view["your_player_id"] = player_id
        view["valid_actions"] = self.get_valid_actions(state, player_id)
        return view

    def get_valid_actions(self, state, player_id):
        if state["game_over"]:
            return []
        player_idx = self._player_index(state, player_id)
        if player_idx is None:
            return []

        if state["phase"] == "config":
            return self._valid_config_actions(state, player_idx)
        elif state["phase"] == "play":
            return self._valid_play_actions(state, player_idx)
        return []

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        kind = action.get("kind")
        player_idx = self._player_index(state, player_id)
        if player_idx is None:
            raise ValueError("Unknown player")
        if state["game_over"]:
            raise ValueError("Game is over")

        if kind == "set_mode":
            return self._apply_set_mode(state, player_idx, action)
        elif kind == "place":
            return self._apply_place(state, player_idx, action)
        elif kind == "move":
            return self._apply_move(state, player_idx, action)
        elif kind == "jump":
            return self._apply_jump(state, player_idx, action)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        if state["phase"] == "config":
            return [state["player_ids"][0]]
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        cp = state["current_player"]
        player_name = state["players"][cp]["name"]
        color = state["players"][cp]["color"]
        reserve_count = len(state["reserve"].get(color, []))

        if phase == "config":
            desc = "Select game mode"
        elif phase == "play":
            desc = f"{player_name}'s turn ({reserve_count} pieces in reserve)"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "description": desc,
            "current_player_name": player_name,
            "mode": state.get("mode", "basic"),
        }

    # ── Config ───────────────────────────────────────────

    def _valid_config_actions(self, state, player_idx):
        if player_idx != 0:
            return []
        return [
            {"kind": "set_mode", "mode": "basic"},
            {"kind": "set_mode", "mode": "standard"},
        ]

    def _apply_set_mode(self, state, player_idx, action):
        if state["phase"] != "config" or player_idx != 0:
            raise ValueError("Only host in config phase")

        mode = action.get("mode")
        if mode not in ("basic", "standard"):
            raise ValueError("Invalid mode")

        state["mode"] = mode
        state["phase"] = "play"
        state["current_player"] = 0
        state["is_first_move"] = True

        log = [f"Game mode: {'Basic' if mode == 'basic' else 'Standard'}. White begins!"]
        return ActionResult(state, log=log)

    # ── Valid actions ────────────────────────────────────

    def _valid_play_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []

        color = state["players"][player_idx]["color"]
        actions = []

        # 1) Place from reserve
        reserve = state["reserve"].get(color, [])
        if reserve:
            actions.extend(self._valid_placements(state, color, reserve))

        # 2) Move pieces on board
        actions.extend(self._valid_moves(state, color))

        # 3) Jump (stack) pieces
        actions.extend(self._valid_jumps(state, color))

        return actions

    def _valid_placements(self, state, color, reserve):
        """Generate all valid place actions."""
        actions = []
        # Group reserve by shape to avoid duplicate rotations for same shape
        seen_shapes = set()
        for pid in reserve:
            shape = get_piece_shape_from_id(pid)
            if shape in seen_shapes:
                continue
            seen_shapes.add(shape)

            rotations = ROTATIONS[shape]
            for rot_idx in range(len(rotations)):
                for key in ALL_POSITIONS:
                    q, r = parse_hex(key)
                    cells = compute_piece_cells(q, r, shape, rot_idx)
                    if cells is None:
                        continue

                    # All cells must be empty
                    if any(state["pieces"].get(c) is not None for c in cells):
                        # Check grid instead
                        grid = build_grid(state["pieces"])
                        if any(c in grid and grid[c] for c in cells):
                            continue

                    # Check grid for occupied cells
                    grid = build_grid(state["pieces"])
                    occupied = False
                    for c in cells:
                        if c in grid and grid[c]:
                            occupied = True
                            break
                    if occupied:
                        continue

                    # First move: no cells in central hexagon
                    if state["is_first_move"]:
                        if any(is_central(*parse_hex(c)) for c in cells):
                            continue

                    # Standard mode: new pieces cannot be placed in central hex
                    if state["mode"] == "standard":
                        if any(is_central(*parse_hex(c)) for c in cells):
                            continue

                    # Find the actual piece_id to use
                    actual_pid = None
                    for rpid in reserve:
                        if get_piece_shape_from_id(rpid) == shape:
                            actual_pid = rpid
                            break

                    if actual_pid:
                        actions.append({
                            "kind": "place",
                            "piece_id": actual_pid,
                            "punct_pos": key,
                            "rotation_idx": rot_idx,
                        })

        return actions

    def _valid_moves(self, state, color):
        """Generate valid move actions (board-level moves)."""
        actions = []
        grid = build_grid(state["pieces"])

        for pid, piece in state["pieces"].items():
            if piece["color"] != color:
                continue
            if piece["level"] != 1:
                continue  # Only ground-level pieces can "move" (not jump)
            if is_piece_blocked(state["pieces"], pid):
                continue

            pq, pr = parse_hex(piece["punct_pos"])
            shape = piece["shape"]

            # PUNCT moves in straight line to any empty position
            for dq, dr in [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]:
                nq, nr = pq + dq, pr + dr
                while is_valid(nq, nr):
                    # Check if we can place piece here with some rotation
                    for rot_idx in range(len(ROTATIONS[shape])):
                        cells = compute_piece_cells(nq, nr, shape, rot_idx)
                        if cells is None:
                            continue

                        # All cells must be empty (ignoring our own piece's current cells)
                        own_cells = set(get_piece_cells(piece))
                        valid = True
                        for c in cells:
                            if c in own_cells:
                                continue  # our piece is moving away from here
                            if c in grid and grid[c]:
                                # Check if it's only our piece
                                occupants = [(p, l) for p, l in grid[c] if p != pid]
                                if occupants:
                                    valid = False
                                    break

                        if valid:
                            actions.append({
                                "kind": "move",
                                "piece_id": pid,
                                "new_punct_pos": hex_key(nq, nr),
                                "rotation_idx": rot_idx,
                            })

                    nq += dq
                    nr += dr

        return actions

    def _valid_jumps(self, state, color):
        """Generate valid jump (stacking) actions."""
        actions = []
        grid = build_grid(state["pieces"])

        for pid, piece in state["pieces"].items():
            if piece["color"] != color:
                continue
            if is_piece_blocked(state["pieces"], pid):
                continue

            pq, pr = parse_hex(piece["punct_pos"])
            shape = piece["shape"]

            # PUNCT moves in straight line, must land on own piece
            for dq, dr in [(1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1)]:
                nq, nr = pq + dq, pr + dr
                while is_valid(nq, nr):
                    nk = hex_key(nq, nr)
                    # PUNCT must land on own piece
                    top_at_punct = get_top_piece_at(grid, state["pieces"], nk)
                    if top_at_punct and state["pieces"][top_at_punct]["color"] == color and top_at_punct != pid:
                        target_level = state["pieces"][top_at_punct]["level"]
                        new_level = target_level + 1

                        for rot_idx in range(len(ROTATIONS[shape])):
                            cells = compute_piece_cells(nq, nr, shape, rot_idx)
                            if cells is None:
                                continue

                            # Validate: PUNCT on own piece, minor dots on any piece or bridge
                            own_cells = set(get_piece_cells(piece))
                            valid = True

                            for ci, c in enumerate(cells):
                                if c in own_cells and c != nk:
                                    pass  # moving away from this cell
                                if ci == 0:
                                    # PUNCT - already validated on own piece above
                                    continue
                                # Minor dots: must land on some piece at appropriate level
                                # or form a bridge
                                top = get_top_piece_at(grid, state["pieces"], c)
                                if top and top != pid:
                                    top_level = state["pieces"][top]["level"]
                                    if top_level != target_level:
                                        valid = False  # not at same level
                                        break
                                elif not top or top == pid:
                                    # Unsupported — only valid if bridging
                                    # For now, allow and check bridge separately
                                    pass

                            if valid:
                                actions.append({
                                    "kind": "jump",
                                    "piece_id": pid,
                                    "new_punct_pos": hex_key(nq, nr),
                                    "rotation_idx": rot_idx,
                                })

                    nq += dq
                    nr += dr

        return actions

    # ── Apply actions ────────────────────────────────────

    def _apply_place(self, state, player_idx, action):
        if state["phase"] != "play" or player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        pid = action.get("piece_id")
        punct_pos = action.get("punct_pos")
        rot_idx = action.get("rotation_idx", 0)

        color = state["players"][player_idx]["color"]
        reserve = state["reserve"].get(color, [])

        if pid not in reserve:
            raise ValueError("Piece not in reserve")

        shape = get_piece_shape_from_id(pid)
        pq, pr = parse_hex(punct_pos)
        cells = compute_piece_cells(pq, pr, shape, rot_idx)
        if cells is None:
            raise ValueError("Invalid placement — cells off board")

        # Validate empty
        grid = build_grid(state["pieces"])
        for c in cells:
            if c in grid and grid[c]:
                raise ValueError("Cells not empty")

        # First move / standard mode: no central hex
        if state["is_first_move"] or state["mode"] == "standard":
            if any(is_central(*parse_hex(c)) for c in cells):
                raise ValueError("Cannot place in central hexagon")

        # Place the piece
        piece = create_piece(pid, color, shape, cells[0], [cells[1], cells[2]], level=1)
        state["pieces"][pid] = piece
        reserve.remove(pid)

        state["is_first_move"] = False

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} placed {shape} piece at {punct_pos}."]

        return self._check_win_and_advance(state, player_idx, log)

    def _apply_move(self, state, player_idx, action):
        if state["phase"] != "play" or player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        pid = action.get("piece_id")
        new_punct = action.get("new_punct_pos")
        rot_idx = action.get("rotation_idx", 0)

        if pid not in state["pieces"]:
            raise ValueError("Piece not on board")

        piece = state["pieces"][pid]
        color = state["players"][player_idx]["color"]

        if piece["color"] != color:
            raise ValueError("Not your piece")
        if is_piece_blocked(state["pieces"], pid):
            raise ValueError("Piece is blocked")

        # Validate straight line
        old_pq, old_pr = parse_hex(piece["punct_pos"])
        new_pq, new_pr = parse_hex(new_punct)
        direction = is_straight_line(old_pq, old_pr, new_pq, new_pr)
        if direction is None:
            raise ValueError("PUNCT must move in a straight line")

        shape = piece["shape"]
        cells = compute_piece_cells(new_pq, new_pr, shape, rot_idx)
        if cells is None:
            raise ValueError("Invalid position — cells off board")

        # Remove piece temporarily, check cells are empty
        old_cells = set(get_piece_cells(piece))
        del state["pieces"][pid]
        grid = build_grid(state["pieces"])

        for c in cells:
            if c in grid and grid[c]:
                state["pieces"][pid] = piece  # restore
                raise ValueError("Destination cells occupied")

        # Place at new position
        new_piece = create_piece(pid, color, shape, cells[0], [cells[1], cells[2]], level=1)
        state["pieces"][pid] = new_piece

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} moved {shape} piece to {new_punct}."]

        return self._check_win_and_advance(state, player_idx, log)

    def _apply_jump(self, state, player_idx, action):
        if state["phase"] != "play" or player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        pid = action.get("piece_id")
        new_punct = action.get("new_punct_pos")
        rot_idx = action.get("rotation_idx", 0)

        if pid not in state["pieces"]:
            raise ValueError("Piece not on board")

        piece = state["pieces"][pid]
        color = state["players"][player_idx]["color"]

        if piece["color"] != color:
            raise ValueError("Not your piece")
        if is_piece_blocked(state["pieces"], pid):
            raise ValueError("Piece is blocked")

        # Validate straight line
        old_pq, old_pr = parse_hex(piece["punct_pos"])
        new_pq, new_pr = parse_hex(new_punct)
        direction = is_straight_line(old_pq, old_pr, new_pq, new_pr)
        if direction is None:
            raise ValueError("PUNCT must move in a straight line")

        shape = piece["shape"]
        cells = compute_piece_cells(new_pq, new_pr, shape, rot_idx)
        if cells is None:
            raise ValueError("Invalid position — cells off board")

        # PUNCT must land on own piece
        # Temporarily remove this piece to check what's beneath
        del state["pieces"][pid]
        grid = build_grid(state["pieces"])

        punct_top = get_top_piece_at(grid, state["pieces"], cells[0])
        if not punct_top or state["pieces"][punct_top]["color"] != color:
            state["pieces"][pid] = piece  # restore
            raise ValueError("PUNCT must land on your own piece")

        target_level = state["pieces"][punct_top]["level"]
        new_level = target_level + 1

        # Restore and create new piece at higher level
        new_piece = create_piece(pid, color, shape, cells[0], [cells[1], cells[2]], level=new_level)
        state["pieces"][pid] = new_piece

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} jumped {shape} piece to {new_punct} (level {new_level})."]

        return self._check_win_and_advance(state, player_idx, log)

    # ── Win check & turn advance ─────────────────────────

    def _check_win_and_advance(self, state, player_idx, log):
        # Check connection for both players
        for idx, player in enumerate(state["players"]):
            if check_connection(state["pieces"], player["color"]):
                state["game_over"] = True
                state["phase"] = "game_over"
                state["winner"] = player["player_id"]
                log.append(f"{player['name']} connected opposite sides and wins!")
                return ActionResult(state, log=log, game_over=True)

        # Check if all pieces placed (standard mode tiebreaker)
        white_reserve = len(state["reserve"].get("white", []))
        black_reserve = len(state["reserve"].get("black", []))

        if white_reserve == 0 and black_reserve == 0:
            if state["mode"] == "standard":
                # Count central hexagon dots
                w_central = count_central_dots(state["pieces"], "white")
                b_central = count_central_dots(state["pieces"], "black")
                log.append(f"All pieces placed! Central hex — White: {w_central}, Black: {b_central}")

                if w_central > b_central:
                    state["game_over"] = True
                    state["phase"] = "game_over"
                    state["winner"] = state["players"][0]["player_id"]
                    log.append(f"{state['players'][0]['name']} wins by central control!")
                elif b_central > w_central:
                    state["game_over"] = True
                    state["phase"] = "game_over"
                    state["winner"] = state["players"][1]["player_id"]
                    log.append(f"{state['players'][1]['name']} wins by central control!")
                else:
                    state["game_over"] = True
                    state["phase"] = "game_over"
                    state["winner"] = None
                    log.append("Draw!")
                return ActionResult(state, log=log, game_over=True)
            else:
                # Basic mode: game ends undecided if no connection
                state["game_over"] = True
                state["phase"] = "game_over"
                state["winner"] = None
                log.append("All pieces placed with no connection — game is a draw!")
                return ActionResult(state, log=log, game_over=True)

        # Advance turn
        state["current_player"] = 1 - state["current_player"]
        return ActionResult(state, log=log)

    # ── Helpers ──────────────────────────────────────────

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
