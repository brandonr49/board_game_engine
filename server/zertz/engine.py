"""ZERTZ game engine — GameEngine subclass."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.zertz.state import (
    POOL_NORMAL, POOL_BLITZ, WIN_NORMAL, WIN_BLITZ, MARBLE_COLORS,
    hex_key, parse_hex, generate_board, create_player,
    find_free_rings, find_single_jumps, find_all_captures, has_any_capture,
    find_isolated_marbles, check_win,
)


class ZertzEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "zertz",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "pool": dict(POOL_NORMAL),
            "current_player": 0,
            "mode": "normal",
            "win_conditions": dict(WIN_NORMAL),
            "phase": "config",
            "sub_phase": None,
            "must_capture": False,
            "capture_position": None,  # position of marble mid-capture-sequence
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

        phase = state["phase"]
        if phase == "config":
            return self._valid_config_actions(state, player_idx)
        elif phase == "play":
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
        elif kind == "place_marble":
            return self._apply_place_marble(state, player_idx, action)
        elif kind == "capture":
            return self._apply_capture(state, player_idx, action)
        elif kind == "remove_ring":
            return self._apply_remove_ring(state, player_idx, action)
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

        if phase == "config":
            desc = "Select game mode"
        elif phase == "play":
            sub = state.get("sub_phase")
            if sub == "place_or_capture":
                if state.get("must_capture"):
                    desc = f"{player_name} — must capture"
                else:
                    desc = f"{player_name} — place a marble"
            elif sub == "remove_ring":
                desc = f"{player_name} — remove a ring"
            elif sub == "capture_sequence":
                desc = f"{player_name} — continue capturing"
            else:
                desc = f"{player_name}'s turn"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "sub_phase": state.get("sub_phase"),
            "must_capture": state.get("must_capture", False),
            "description": desc,
            "current_player_name": player_name,
        }

    # ── Config phase ─────────────────────────────────────

    def _valid_config_actions(self, state, player_idx):
        if player_idx != 0:
            return []
        return [
            {"kind": "set_mode", "mode": "normal"},
            {"kind": "set_mode", "mode": "blitz"},
        ]

    def _apply_set_mode(self, state, player_idx, action):
        if state["phase"] != "config":
            raise ValueError("Not in config phase")
        if player_idx != 0:
            raise ValueError("Only the host can set the mode")

        mode = action.get("mode")
        if mode not in ("normal", "blitz"):
            raise ValueError("Mode must be 'normal' or 'blitz'")

        if mode == "blitz":
            state["pool"] = dict(POOL_BLITZ)
            state["win_conditions"] = dict(WIN_BLITZ)
        else:
            state["pool"] = dict(POOL_NORMAL)
            state["win_conditions"] = dict(WIN_NORMAL)

        state["mode"] = mode
        state["phase"] = "play"
        state["sub_phase"] = "place_or_capture"
        state["must_capture"] = False  # no marbles on board yet

        mode_name = "Normal" if mode == "normal" else "Blitz"
        log = [f"Game mode: {mode_name}. Place marbles and shrink the board!"]
        return ActionResult(state, log=log)

    # ── Play phase: valid actions ────────────────────────

    def _valid_play_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []

        sub = state.get("sub_phase")

        if sub == "place_or_capture":
            return self._valid_place_or_capture(state, player_idx)
        elif sub == "remove_ring":
            return self._valid_remove_ring(state)
        elif sub == "capture_sequence":
            return self._valid_capture_continuation(state)
        return []

    def _valid_place_or_capture(self, state, player_idx):
        board = state["board"]
        actions = []

        # Check for mandatory captures
        if has_any_capture(board):
            # Must capture — offer all possible first jumps
            for key, marble in board.items():
                if marble is None:
                    continue
                jumps = find_single_jumps(board, key)
                for jump in jumps:
                    actions.append({
                        "kind": "capture",
                        "from": key,
                        "to": jump["to"],
                    })
            return actions

        # No captures — offer placements
        pool = state["pool"]
        available_colors = [c for c in MARBLE_COLORS if pool.get(c, 0) > 0]

        for color in available_colors:
            for key, val in board.items():
                if val is None:  # vacant ring
                    actions.append({
                        "kind": "place_marble",
                        "color": color,
                        "position": key,
                    })

        return actions

    def _valid_remove_ring(self, state):
        free = find_free_rings(state["board"])
        return [{"kind": "remove_ring", "ring": key} for key in free]

    def _valid_capture_continuation(self, state):
        pos = state.get("capture_position")
        if not pos:
            return []
        jumps = find_single_jumps(state["board"], pos)
        return [{"kind": "capture", "from": pos, "to": j["to"]} for j in jumps]

    # ── Play phase: apply actions ────────────────────────

    def _apply_place_marble(self, state, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "place_or_capture":
            raise ValueError("Not in place_or_capture phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        # Mandatory capture check
        if has_any_capture(state["board"]):
            raise ValueError("You must capture — a jump is available")

        color = action.get("color")
        position = action.get("position")

        if color not in MARBLE_COLORS:
            raise ValueError(f"Invalid marble color: {color}")
        if state["pool"].get(color, 0) <= 0:
            raise ValueError(f"No {color} marbles in the pool")
        if position not in state["board"]:
            raise ValueError("Invalid position")
        if state["board"][position] is not None:
            raise ValueError("Position is occupied")

        state["board"][position] = color
        state["pool"][color] -= 1

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} placed a {color} marble at {position}."]

        # Check for free rings to remove
        free = find_free_rings(state["board"])
        if free:
            state["sub_phase"] = "remove_ring"
            return ActionResult(state, log=log)

        # No free rings — skip removal, advance turn
        log.append("No free rings to remove.")
        return self._advance_turn(state, log)

    def _apply_capture(self, state, player_idx, action):
        if state["phase"] != "play":
            raise ValueError("Not in play phase")
        sub = state.get("sub_phase")
        if sub not in ("place_or_capture", "capture_sequence"):
            raise ValueError("Not in capture phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        from_key = action.get("from")
        to_key = action.get("to")
        if not from_key or not to_key:
            raise ValueError("Missing from or to")

        board = state["board"]
        if from_key not in board or board[from_key] is None:
            raise ValueError("No marble at source")

        # Validate the jump
        jumps = find_single_jumps(board, from_key)
        valid_jump = None
        for j in jumps:
            if j["to"] == to_key:
                valid_jump = j
                break

        if valid_jump is None:
            raise ValueError("Invalid capture move")

        # Execute the jump
        marble_color = board[from_key]
        captured_color = board[valid_jump["captured"]]

        board[to_key] = marble_color
        board[from_key] = None
        board[valid_jump["captured"]] = None

        # Add captured marble to player
        player = state["players"][player_idx]
        player["captured"][captured_color] += 1

        player_name = player["name"]
        log = [f"{player_name} captured a {captured_color} marble at {valid_jump['captured']}."]

        # Check for more jumps from landing position
        more_jumps = find_single_jumps(board, to_key)
        if more_jumps:
            state["sub_phase"] = "capture_sequence"
            state["capture_position"] = to_key
            log.append("Multi-jump available — must continue!")
            return ActionResult(state, log=log)

        # Capture sequence complete
        state["capture_position"] = None

        # Check win
        if check_win(player["captured"], state["win_conditions"]):
            return self._end_game_winner(state, player_idx, log)

        return self._advance_turn(state, log)

    def _apply_remove_ring(self, state, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "remove_ring":
            raise ValueError("Not in remove_ring phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        ring_key = action.get("ring")
        if not ring_key or ring_key not in state["board"]:
            raise ValueError("Invalid ring position")
        if state["board"][ring_key] is not None:
            raise ValueError("Ring is occupied")

        # Validate it's a free ring
        free = find_free_rings(state["board"])
        if ring_key not in free:
            raise ValueError("Ring is not removable")

        # Remove the ring
        del state["board"][ring_key]

        player = state["players"][player_idx]
        player_name = player["name"]
        log = [f"{player_name} removed ring at {ring_key}."]

        # Check for isolated marbles
        isolated = find_isolated_marbles(state["board"])
        if isolated:
            for key, marble_color in isolated:
                player["captured"][marble_color] += 1
                state["board"][key] = None
                # Also remove the isolated rings
            # Remove all isolated rings
            main_keys = self._get_main_component(state["board"])
            keys_to_remove = set(state["board"].keys()) - main_keys
            for key in keys_to_remove:
                del state["board"][key]

            log.append(f"{player_name} claimed {len(isolated)} isolated marble(s).")

        # Check win
        if check_win(player["captured"], state["win_conditions"]):
            return self._end_game_winner(state, player_idx, log)

        return self._advance_turn(state, log)

    # ── Turn advancement ─────────────────────────────────

    def _advance_turn(self, state, log):
        state["current_player"] = 1 - state["current_player"]
        state["sub_phase"] = "place_or_capture"
        state["capture_position"] = None

        # Check if pool is empty and no captures available
        pool_empty = all(v == 0 for v in state["pool"].values())
        no_captures = not has_any_capture(state["board"])
        no_vacant = all(v is not None for v in state["board"].values())

        if pool_empty and no_captures:
            return self._end_game(state, log)
        if no_vacant and no_captures:
            return self._end_game(state, log)

        # Update must_capture flag for next player
        state["must_capture"] = has_any_capture(state["board"])

        return ActionResult(state, log=log)

    # ── Helpers ──────────────────────────────────────────

    def _get_main_component(self, board):
        """Return set of keys in the largest connected component."""
        if not board:
            return set()
        start = next(iter(board))
        visited = {start}
        queue = [start]
        while queue:
            current = queue.pop(0)
            cq, cr = parse_hex(current)
            from server.zertz.state import AXIAL_DIRS
            for dq, dr in AXIAL_DIRS:
                nkey = hex_key(cq + dq, cr + dr)
                if nkey in board and nkey not in visited:
                    visited.add(nkey)
                    queue.append(nkey)
        return visited

    def _end_game_winner(self, state, winner_idx, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None
        state["winner"] = state["players"][winner_idx]["player_id"]
        p = state["players"][winner_idx]
        log.append(f"{p['name']} wins! (W:{p['captured']['white']} "
                   f"G:{p['captured']['gray']} B:{p['captured']['black']})")
        return ActionResult(state, log=log, game_over=True)

    def _end_game(self, state, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None

        p0 = state["players"][0]
        p1 = state["players"][1]
        t0 = sum(p0["captured"].values())
        t1 = sum(p1["captured"].values())

        log.append(f"Game over! {p0['name']}: {t0} marbles, {p1['name']}: {t1} marbles.")

        if t0 > t1:
            state["winner"] = p0["player_id"]
            log.append(f"{p0['name']} wins!")
        elif t1 > t0:
            state["winner"] = p1["player_id"]
            log.append(f"{p1['name']} wins!")
        else:
            state["winner"] = None
            log.append("It's a draw!")

        return ActionResult(state, log=log, game_over=True)

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
