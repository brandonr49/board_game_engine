"""YINSH game engine — GameEngine subclass."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.yinsh.state import (
    RINGS_PER_PLAYER, TOTAL_MARKERS, ROW_LENGTH,
    hex_key, parse_hex, generate_board, create_player,
    find_ring_moves, find_rows, rows_are_intersecting,
)


class YinshEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "yinsh",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "markers_remaining": TOTAL_MARKERS,
            "current_player": 0,
            "rings_to_win": 3,
            "phase": "config",
            "sub_phase": None,
            "rings_placed": 0,
            "active_ring": None,
            "pending_rows": [],
            "opponent_pending_rows": [],
            "row_player": None,  # which player is currently removing rows
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
        elif phase == "placement":
            return self._valid_placement_actions(state, player_idx)
        elif phase == "main":
            return self._valid_main_actions(state, player_id, player_idx)
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
        elif kind == "place_ring":
            return self._apply_place_ring(state, player_idx, action)
        elif kind == "place_marker":
            return self._apply_place_marker(state, player_idx, action)
        elif kind == "move_ring":
            return self._apply_move_ring(state, player_idx, action)
        elif kind == "select_row":
            return self._apply_select_row(state, player_idx, action)
        elif kind == "remove_ring":
            return self._apply_remove_ring(state, player_idx, action)
        elif kind == "pass":
            return self._apply_pass(state, player_idx)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        if state["phase"] == "config":
            return [state["player_ids"][0]]
        sub = state.get("sub_phase")
        if sub in ("remove_row", "remove_ring") and state.get("row_player") is not None:
            return [state["player_ids"][state["row_player"]]]
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        cp = state["current_player"]
        player_name = state["players"][cp]["name"]

        if phase == "config":
            desc = "Select game mode"
        elif phase == "placement":
            desc = f"{player_name} — place a ring"
        elif phase == "main":
            sub = state.get("sub_phase")
            rp = state.get("row_player")
            if sub == "place_marker":
                desc = f"{player_name} — place a marker in a ring"
            elif sub == "move_ring":
                desc = f"{player_name} — move your ring"
            elif sub == "remove_row":
                rname = state["players"][rp]["name"] if rp is not None else player_name
                desc = f"{rname} — select a row to remove"
            elif sub == "remove_ring":
                rname = state["players"][rp]["name"] if rp is not None else player_name
                desc = f"{rname} — remove one of your rings"
            else:
                desc = f"{player_name}'s turn"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "sub_phase": state.get("sub_phase"),
            "rings_to_win": state["rings_to_win"],
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

        state["rings_to_win"] = 3 if mode == "normal" else 1
        state["phase"] = "placement"
        state["current_player"] = 0

        mode_name = "Normal (3 rings)" if mode == "normal" else "Blitz (1 ring)"
        log = [f"Game mode: {mode_name}. Place your rings!"]
        return ActionResult(state, log=log)

    # ── Placement phase ──────────────────────────────────

    def _valid_placement_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []
        actions = []
        for key, cell in state["board"].items():
            if cell is None:
                actions.append({"kind": "place_ring", "position": key})
        return actions

    def _apply_place_ring(self, state, player_idx, action):
        if state["phase"] != "placement":
            raise ValueError("Not in placement phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        position = action.get("position")
        if not position or position not in state["board"]:
            raise ValueError("Invalid position")
        if state["board"][position] is not None:
            raise ValueError("Position is occupied")

        player = state["players"][player_idx]
        state["board"][position] = {"type": "ring", "color": player["color"]}
        player["rings_on_board"] += 1
        state["rings_placed"] += 1

        log = [f"{player['name']} placed a ring at {position}."]

        if state["rings_placed"] >= RINGS_PER_PLAYER * 2:
            state["phase"] = "main"
            state["sub_phase"] = "place_marker"
            state["current_player"] = 0
            log.append("All rings placed! Movement phase begins.")
        else:
            state["current_player"] = 1 - state["current_player"]

        return ActionResult(state, log=log)

    # ── Main phase: valid actions ────────────────────────

    def _valid_main_actions(self, state, player_id, player_idx):
        sub = state.get("sub_phase")

        if sub == "place_marker":
            if player_idx != state["current_player"]:
                return []
            # List all rings belonging to this player
            player_color = state["players"][player_idx]["color"]
            actions = []
            for key, cell in state["board"].items():
                if cell and cell["type"] == "ring" and cell["color"] == player_color:
                    actions.append({"kind": "place_marker", "ring": key})
            if not actions:
                actions = [{"kind": "pass"}]
            return actions

        elif sub == "move_ring":
            if player_idx != state["current_player"]:
                return []
            active = state.get("active_ring")
            if not active:
                return []
            moves = find_ring_moves(state["board"], active)
            return [{"kind": "move_ring", "to": m["to"]} for m in moves]

        elif sub == "remove_row":
            rp = state.get("row_player")
            if player_idx != rp:
                return []
            # Determine which pending rows to offer
            if rp == state["current_player"]:
                rows = state.get("pending_rows", [])
            else:
                rows = state.get("opponent_pending_rows", [])
            return [{"kind": "select_row", "row": row} for row in rows]

        elif sub == "remove_ring":
            rp = state.get("row_player")
            if player_idx != rp:
                return []
            player_color = state["players"][player_idx]["color"]
            actions = []
            for key, cell in state["board"].items():
                if cell and cell["type"] == "ring" and cell["color"] == player_color:
                    actions.append({"kind": "remove_ring", "ring": key})
            return actions

        return []

    # ── Main phase: apply actions ────────────────────────

    def _apply_place_marker(self, state, player_idx, action):
        if state["phase"] != "main" or state.get("sub_phase") != "place_marker":
            raise ValueError("Not in place_marker phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        ring_key = action.get("ring")
        if not ring_key or ring_key not in state["board"]:
            raise ValueError("Invalid ring position")

        cell = state["board"][ring_key]
        player = state["players"][player_idx]

        if not cell or cell["type"] != "ring" or cell["color"] != player["color"]:
            raise ValueError("No ring of yours at that position")
        if state["markers_remaining"] <= 0:
            raise ValueError("No markers remaining")

        # Replace ring with marker, ring is "lifted"
        state["board"][ring_key] = {"type": "marker", "color": player["color"]}
        state["markers_remaining"] -= 1
        state["active_ring"] = ring_key
        state["sub_phase"] = "move_ring"

        log = [f"{player['name']} placed a marker at {ring_key}."]
        return ActionResult(state, log=log)

    def _apply_move_ring(self, state, player_idx, action):
        if state["phase"] != "main" or state.get("sub_phase") != "move_ring":
            raise ValueError("Not in move_ring phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        to_key = action.get("to")
        active = state.get("active_ring")
        if not to_key or not active:
            raise ValueError("Missing destination or no active ring")

        # Validate move
        moves = find_ring_moves(state["board"], active)
        valid_move = None
        for m in moves:
            if m["to"] == to_key:
                valid_move = m
                break

        if valid_move is None:
            raise ValueError("Invalid ring destination")

        player = state["players"][player_idx]

        # Place ring at destination
        state["board"][to_key] = {"type": "ring", "color": player["color"]}

        # Flip jumped markers
        for flip_key in valid_move["flipped"]:
            cell = state["board"][flip_key]
            if cell and cell["type"] == "marker":
                cell["color"] = "white" if cell["color"] == "black" else "black"

        state["active_ring"] = None

        log = [f"{player['name']} moved ring to {to_key}."]
        if valid_move["flipped"]:
            log.append(f"Flipped {len(valid_move['flipped'])} marker(s).")

        # Check for rows of 5
        return self._check_rows_after_move(state, player_idx, log)

    def _apply_pass(self, state, player_idx):
        if state["phase"] != "main" or state.get("sub_phase") != "place_marker":
            raise ValueError("Can only pass during place_marker")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        # Verify no rings to place markers in
        player_color = state["players"][player_idx]["color"]
        has_rings = any(
            cell and cell["type"] == "ring" and cell["color"] == player_color
            for cell in state["board"].values()
        )
        if has_rings:
            raise ValueError("You have rings — cannot pass")

        player = state["players"][player_idx]
        log = [f"{player['name']} passed (no rings on board)."]

        state["current_player"] = 1 - state["current_player"]

        # Check if next player also can't move
        next_color = state["players"][state["current_player"]]["color"]
        next_has_rings = any(
            cell and cell["type"] == "ring" and cell["color"] == next_color
            for cell in state["board"].values()
        )
        if not next_has_rings:
            return self._end_game(state, log)

        return ActionResult(state, log=log)

    # ── Row handling ─────────────────────────────────────

    def _check_rows_after_move(self, state, player_idx, log):
        """After a ring move, detect rows for both players and enter removal flow."""
        player_color = state["players"][player_idx]["color"]
        opp_color = state["players"][1 - player_idx]["color"]

        my_rows = find_rows(state["board"], player_color)
        opp_rows = find_rows(state["board"], opp_color)

        state["pending_rows"] = my_rows
        state["opponent_pending_rows"] = opp_rows

        if my_rows:
            state["sub_phase"] = "remove_row"
            state["row_player"] = player_idx
            log.append(f"{state['players'][player_idx]['name']} formed {len(my_rows)} row(s)!")
            return ActionResult(state, log=log)

        if opp_rows:
            state["sub_phase"] = "remove_row"
            state["row_player"] = 1 - player_idx
            log.append(f"{state['players'][1 - player_idx]['name']} formed {len(opp_rows)} row(s)!")
            return ActionResult(state, log=log)

        # No rows — check markers exhaustion, then advance turn
        if state["markers_remaining"] <= 0:
            return self._end_game(state, log)

        return self._advance_turn(state, log)

    def _apply_select_row(self, state, player_idx, action):
        if state["phase"] != "main" or state.get("sub_phase") != "remove_row":
            raise ValueError("Not in remove_row phase")

        rp = state.get("row_player")
        if player_idx != rp:
            raise ValueError("Not your turn to remove a row")

        row = action.get("row")
        if not row or len(row) != ROW_LENGTH:
            raise ValueError(f"Row must contain exactly {ROW_LENGTH} positions")

        # Validate the row is in the pending rows list
        if rp == state["current_player"]:
            pending = state.get("pending_rows", [])
        else:
            pending = state.get("opponent_pending_rows", [])

        row_set = set(row)
        valid = False
        for pr in pending:
            if set(pr) == row_set:
                valid = True
                break

        if not valid:
            raise ValueError("Selected row is not a valid pending row")

        # Remove the 5 markers
        for key in row:
            state["board"][key] = None
        state["markers_remaining"] += ROW_LENGTH

        player = state["players"][player_idx]
        log = [f"{player['name']} removed a row of 5 markers."]

        # Remove this row and any rows that intersected with it from pending
        if rp == state["current_player"]:
            state["pending_rows"] = [
                r for r in state["pending_rows"]
                if not row_set.intersection(set(r))
            ]
        else:
            state["opponent_pending_rows"] = [
                r for r in state["opponent_pending_rows"]
                if not row_set.intersection(set(r))
            ]

        # Now player must remove one of their rings
        state["sub_phase"] = "remove_ring"
        return ActionResult(state, log=log)

    def _apply_remove_ring(self, state, player_idx, action):
        if state["phase"] != "main" or state.get("sub_phase") != "remove_ring":
            raise ValueError("Not in remove_ring phase")

        rp = state.get("row_player")
        if player_idx != rp:
            raise ValueError("Not your turn to remove a ring")

        ring_key = action.get("ring")
        if not ring_key or ring_key not in state["board"]:
            raise ValueError("Invalid ring position")

        cell = state["board"][ring_key]
        player = state["players"][player_idx]

        if not cell or cell["type"] != "ring" or cell["color"] != player["color"]:
            raise ValueError("No ring of yours at that position")

        state["board"][ring_key] = None
        player["rings_on_board"] -= 1
        player["rings_removed"] += 1

        log = [f"{player['name']} removed a ring ({player['rings_removed']}/{state['rings_to_win']})."]

        # Check win condition
        if player["rings_removed"] >= state["rings_to_win"]:
            return self._end_game_winner(state, player_idx, log)

        # Check if this player has more pending rows
        if rp == state["current_player"]:
            remaining = state.get("pending_rows", [])
        else:
            remaining = state.get("opponent_pending_rows", [])

        # Re-detect rows since board changed
        player_color = player["color"]
        new_rows = find_rows(state["board"], player_color)

        if rp == state["current_player"]:
            state["pending_rows"] = new_rows
        else:
            state["opponent_pending_rows"] = new_rows

        if new_rows:
            state["sub_phase"] = "remove_row"
            return ActionResult(state, log=log)

        # This player done. Check if the OTHER player has pending rows
        if rp == state["current_player"] and state.get("opponent_pending_rows"):
            # Re-detect opponent rows (board may have changed)
            opp_color = state["players"][1 - rp]["color"]
            opp_rows = find_rows(state["board"], opp_color)
            state["opponent_pending_rows"] = opp_rows
            if opp_rows:
                state["row_player"] = 1 - rp
                state["sub_phase"] = "remove_row"
                log.append(f"{state['players'][1 - rp]['name']} must remove their row(s).")
                return ActionResult(state, log=log)

        # All rows handled — advance turn
        state["pending_rows"] = []
        state["opponent_pending_rows"] = []
        state["row_player"] = None

        if state["markers_remaining"] <= 0:
            return self._end_game(state, log)

        return self._advance_turn(state, log)

    # ── Turn advancement ─────────────────────────────────

    def _advance_turn(self, state, log):
        state["current_player"] = 1 - state["current_player"]
        state["sub_phase"] = "place_marker"
        state["active_ring"] = None
        state["pending_rows"] = []
        state["opponent_pending_rows"] = []
        state["row_player"] = None
        return ActionResult(state, log=log)

    # ── Game end ─────────────────────────────────────────

    def _end_game_winner(self, state, winner_idx, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None
        state["winner"] = state["players"][winner_idx]["player_id"]
        log.append(f"{state['players'][winner_idx]['name']} wins!")
        return ActionResult(state, log=log, game_over=True)

    def _end_game(self, state, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None

        p0 = state["players"][0]
        p1 = state["players"][1]

        log.append(f"Game over! {p0['name']}: {p0['rings_removed']} rings removed, "
                   f"{p1['name']}: {p1['rings_removed']} rings removed.")

        if p0["rings_removed"] > p1["rings_removed"]:
            state["winner"] = p0["player_id"]
            log.append(f"{p0['name']} wins!")
        elif p1["rings_removed"] > p0["rings_removed"]:
            state["winner"] = p1["player_id"]
            log.append(f"{p1['name']} wins!")
        else:
            state["winner"] = None
            log.append("It's a draw!")

        return ActionResult(state, log=log, game_over=True)

    # ── Helpers ──────────────────────────────────────────

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
