"""GIPF game engine — GameEngine subclass with Basic, Standard, and Tournament modes."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.gipf.state import (
    hex_key, parse_hex, generate_board, create_player,
    setup_basic, setup_standard,
    EDGE_DOTS, EDGE_DOT_MAP,
    can_push, execute_push, find_rows_of_four,
)


class GipfEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name, 15)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "gipf",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "current_player": 0,
            "mode": "basic",
            "phase": "config",
            "sub_phase": None,
            "pending_rows": [],
            "opponent_pending_rows": [],
            "row_resolver": None,
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
        elif kind == "push":
            return self._apply_push(state, player_idx, action)
        elif kind == "resolve_row":
            return self._apply_resolve_row(state, player_idx, action)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        if state["phase"] == "config":
            return [state["player_ids"][0]]
        if state.get("sub_phase") == "resolve_rows" and state.get("row_resolver") is not None:
            return [state["player_ids"][state["row_resolver"]]]
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        cp = state["current_player"]
        player_name = state["players"][cp]["name"]

        if phase == "config":
            desc = "Select game mode"
        elif phase == "play":
            sub = state.get("sub_phase")
            if sub == "push":
                p = state["players"][cp]
                desc = f"{player_name} — push a piece ({p['reserve']} in reserve)"
            elif sub == "resolve_rows":
                rr = state.get("row_resolver", cp)
                rname = state["players"][rr]["name"]
                desc = f"{rname} — resolve row of 4"
            else:
                desc = f"{player_name}'s turn"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "sub_phase": state.get("sub_phase"),
            "description": desc,
            "current_player_name": player_name,
        }

    # ── Config phase ─────────────────────────────────────

    def _valid_config_actions(self, state, player_idx):
        if player_idx != 0:
            return []
        return [
            {"kind": "set_mode", "mode": "basic"},
            {"kind": "set_mode", "mode": "standard"},
            {"kind": "set_mode", "mode": "tournament"},
        ]

    def _apply_set_mode(self, state, player_idx, action):
        if state["phase"] != "config" or player_idx != 0:
            raise ValueError("Only host can set mode in config phase")

        mode = action.get("mode")
        if mode not in ("basic", "standard", "tournament"):
            raise ValueError("Invalid mode")

        state["mode"] = mode

        if mode == "basic":
            # 15 pieces each, 3 pre-placed = 12 in reserve
            for p in state["players"]:
                p["reserve"] = 12
            setup_basic(state["board"])
        elif mode == "standard":
            # 18 pieces each, 3 GIPF-pieces pre-placed (6 pieces used) = 12 in reserve
            for p in state["players"]:
                p["reserve"] = 12
            setup_standard(state["board"])
        elif mode == "tournament":
            # 18 pieces each, empty board, all in reserve
            for p in state["players"]:
                p["reserve"] = 18

        state["phase"] = "play"
        state["sub_phase"] = "push"
        state["current_player"] = 0

        mode_names = {"basic": "Basic", "standard": "Standard", "tournament": "Tournament"}
        log = [f"Game mode: {mode_names[mode]}. White begins!"]
        return ActionResult(state, log=log)

    # ── Play phase: valid actions ────────────────────────

    def _valid_play_actions(self, state, player_idx):
        sub = state.get("sub_phase")

        if sub == "push":
            if player_idx != state["current_player"]:
                return []
            return self._valid_push_actions(state, player_idx)

        elif sub == "resolve_rows":
            rr = state.get("row_resolver")
            if player_idx != rr:
                return []
            return self._valid_resolve_actions(state, player_idx)

        return []

    def _valid_push_actions(self, state, player_idx):
        player = state["players"][player_idx]
        if player["reserve"] <= 0:
            return []

        mode = state["mode"]
        actions = []

        for dot_info in EDGE_DOTS:
            if not can_push(state["board"], dot_info):
                continue

            if mode == "basic":
                # Only single pieces
                actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": False})
            elif mode == "standard":
                # Can always play single or GIPF (if reserve >= 2 for GIPF)
                actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": False})
                if player["reserve"] >= 2:
                    actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": True})
            elif mode == "tournament":
                if not player["has_played_single"]:
                    # Must play GIPF pieces (can also choose to play single to stop GIPF phase)
                    if player["reserve"] >= 2:
                        actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": True})
                    # Can play single (which locks out future GIPF plays)
                    actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": False})
                else:
                    # Already played single — only single pieces
                    actions.append({"kind": "push", "dot": dot_info["dot_key"], "is_gipf": False})

        return actions

    def _valid_resolve_actions(self, state, player_idx):
        """Offer row resolution choices."""
        player = state["players"][player_idx]
        player_color = player["color"]

        if player_idx == state["current_player"]:
            rows = state.get("pending_rows", [])
        else:
            rows = state.get("opponent_pending_rows", [])

        if not rows:
            return []

        actions = []
        for row in rows:
            # Find GIPF pieces in this row that belong to the resolver
            gipf_in_row = []
            for key in row["keys"]:
                piece = state["board"].get(key)
                if piece and piece["is_gipf"] and piece["color"] == player_color:
                    gipf_in_row.append(key)

            if not gipf_in_row:
                # No GIPF pieces — straightforward removal
                actions.append({
                    "kind": "resolve_row",
                    "row_keys": row["keys"],
                    "keep_gipf": [],
                })
            else:
                # Player can choose to keep or remove each GIPF piece
                # For simplicity: offer "keep all" and "remove all" options
                # Plus individual choices would be too many — keep it simple
                actions.append({
                    "kind": "resolve_row",
                    "row_keys": row["keys"],
                    "keep_gipf": list(gipf_in_row),  # keep all own GIPF
                })
                actions.append({
                    "kind": "resolve_row",
                    "row_keys": row["keys"],
                    "keep_gipf": [],  # remove all
                })

        return actions

    # ── Play phase: apply actions ────────────────────────

    def _apply_push(self, state, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "push":
            raise ValueError("Not in push phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        dot_key = action.get("dot")
        is_gipf = action.get("is_gipf", False)

        if dot_key not in EDGE_DOT_MAP:
            raise ValueError("Invalid edge dot")

        dot_info = EDGE_DOT_MAP[dot_key]
        if not can_push(state["board"], dot_info):
            raise ValueError("Cannot push — line is full")

        player = state["players"][player_idx]
        reserve_cost = 2 if is_gipf else 1

        if player["reserve"] < reserve_cost:
            raise ValueError("Not enough pieces in reserve")

        # Tournament mode: validate GIPF rules
        mode = state["mode"]
        if mode == "tournament" and is_gipf and player["has_played_single"]:
            raise ValueError("Cannot play GIPF pieces after playing a single piece")

        # Execute push
        piece = {"color": player["color"], "is_gipf": is_gipf}
        execute_push(state["board"], dot_info, piece)
        player["reserve"] -= reserve_cost

        # Tournament mode: track first single piece
        if mode == "tournament" and not is_gipf:
            player["has_played_single"] = True

        piece_type = "GIPF-piece" if is_gipf else "piece"
        log = [f"{player['name']} pushed a {piece_type} from {dot_key}."]

        # Check for rows of 4
        return self._check_rows(state, player_idx, log)

    def _apply_resolve_row(self, state, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "resolve_rows":
            raise ValueError("Not in resolve_rows phase")

        rr = state.get("row_resolver")
        if player_idx != rr:
            raise ValueError("Not your turn to resolve rows")

        row_keys = action.get("row_keys", [])
        keep_gipf = set(action.get("keep_gipf", []))

        player = state["players"][player_idx]
        player_color = player["color"]
        opp_idx = 1 - player_idx
        opp = state["players"][opp_idx]

        log = []

        # Remove pieces from the row
        for key in row_keys:
            if key in keep_gipf:
                continue  # Keep this GIPF piece on the board

            piece = state["board"].get(key)
            if piece is None:
                continue

            state["board"][key] = None

            if piece["color"] == player_color:
                # Own pieces return to reserve
                return_count = 2 if piece["is_gipf"] else 1
                player["reserve"] += return_count
            else:
                # Opponent pieces captured
                capture_count = 2 if piece["is_gipf"] else 1
                player["captured_opponent"] += capture_count
                # Don't return to opponent's reserve

        log.append(f"{player['name']} resolved a row.")

        # Remove this row from pending
        if player_idx == state["current_player"]:
            state["pending_rows"] = [
                r for r in state["pending_rows"]
                if set(r["keys"]) != set(row_keys)
            ]
            # Remove intersecting rows too
            removed_set = set(row_keys) - keep_gipf
            state["pending_rows"] = [
                r for r in state["pending_rows"]
                if not removed_set.intersection(set(r["keys"]))
            ]
        else:
            state["opponent_pending_rows"] = [
                r for r in state["opponent_pending_rows"]
                if set(r["keys"]) != set(row_keys)
            ]
            removed_set = set(row_keys) - keep_gipf
            state["opponent_pending_rows"] = [
                r for r in state["opponent_pending_rows"]
                if not removed_set.intersection(set(r["keys"]))
            ]

        # Check win after removal
        win_result = self._check_win(state, log)
        if win_result:
            return win_result

        # Check if more rows to resolve for this player
        if player_idx == state["current_player"] and state["pending_rows"]:
            return ActionResult(state, log=log)

        # Check opponent's rows
        if player_idx == state["current_player"] and state.get("opponent_pending_rows"):
            # Re-detect opponent rows (board changed)
            opp_color = opp["color"]
            opp_rows = find_rows_of_four(state["board"], opp_color)
            state["opponent_pending_rows"] = opp_rows
            if opp_rows:
                state["row_resolver"] = opp_idx
                log.append(f"{opp['name']} must resolve their row(s).")
                return ActionResult(state, log=log)

        if player_idx != state["current_player"] and state.get("opponent_pending_rows"):
            return ActionResult(state, log=log)

        # All rows resolved — advance turn
        state["pending_rows"] = []
        state["opponent_pending_rows"] = []
        state["row_resolver"] = None
        return self._advance_turn(state, log)

    # ── Row detection ────────────────────────────────────

    def _check_rows(self, state, player_idx, log):
        """After a push, detect rows of 4 for both players."""
        player_color = state["players"][player_idx]["color"]
        opp_color = state["players"][1 - player_idx]["color"]

        my_rows = find_rows_of_four(state["board"], player_color)
        opp_rows = find_rows_of_four(state["board"], opp_color)

        state["pending_rows"] = my_rows
        state["opponent_pending_rows"] = opp_rows

        if my_rows:
            state["sub_phase"] = "resolve_rows"
            state["row_resolver"] = player_idx
            log.append(f"{state['players'][player_idx]['name']} formed {len(my_rows)} row(s) of 4!")
            return ActionResult(state, log=log)

        if opp_rows:
            state["sub_phase"] = "resolve_rows"
            state["row_resolver"] = 1 - player_idx
            log.append(f"{state['players'][1 - player_idx]['name']} formed {len(opp_rows)} row(s) of 4!")
            return ActionResult(state, log=log)

        # No rows — check win and advance
        win_result = self._check_win(state, log)
        if win_result:
            return win_result

        return self._advance_turn(state, log)

    # ── Turn advancement ─────────────────────────────────

    def _advance_turn(self, state, log):
        state["current_player"] = 1 - state["current_player"]
        state["sub_phase"] = "push"
        state["pending_rows"] = []
        state["opponent_pending_rows"] = []
        state["row_resolver"] = None

        # Check if next player can play
        next_player = state["players"][state["current_player"]]
        if next_player["reserve"] <= 0:
            winner_idx = 1 - state["current_player"]
            log.append(f"{next_player['name']} has no pieces in reserve!")
            return self._end_game_winner(state, winner_idx, log)

        return ActionResult(state, log=log)

    # ── Win detection ────────────────────────────────────

    def _check_win(self, state, log):
        """Check win conditions based on mode."""
        mode = state["mode"]

        if mode == "basic":
            # Win if opponent has 0 reserve (checked in _advance_turn)
            return None

        # Standard/Tournament: also check GIPF-piece elimination
        for idx, player in enumerate(state["players"]):
            opp_idx = 1 - idx
            opp_color = state["players"][opp_idx]["color"]

            # Count opponent's GIPF pieces on board
            opp_gipf_count = sum(
                1 for piece in state["board"].values()
                if piece and piece["color"] == opp_color and piece["is_gipf"]
            )

            if opp_gipf_count == 0:
                # Check if opponent ever had GIPF pieces
                # In tournament mode, they might not have placed any yet
                if mode == "tournament":
                    # Only counts after opponent has played at least one piece
                    opp_pieces_on_board = sum(
                        1 for piece in state["board"].values()
                        if piece and piece["color"] == opp_color
                    )
                    if opp_pieces_on_board > 0 and state["players"][opp_idx]["has_played_single"]:
                        log.append(f"{state['players'][opp_idx]['name']} has no GIPF pieces!")
                        return self._end_game_winner(state, idx, log)
                elif mode == "standard":
                    log.append(f"{state['players'][opp_idx]['name']} has no GIPF pieces!")
                    return self._end_game_winner(state, idx, log)

        return None

    def _end_game_winner(self, state, winner_idx, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None
        state["winner"] = state["players"][winner_idx]["player_id"]
        log.append(f"{state['players'][winner_idx]['name']} wins!")
        return ActionResult(state, log=log, game_over=True)

    # ── Helpers ──────────────────────────────────────────

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
