"""TZAAR game engine — GameEngine subclass."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.tzaar.state import (
    PIECE_TYPES,
    hex_key, parse_hex, generate_board, create_player,
    setup_random, setup_fixed,
    find_captures, find_stacks, find_line_target,
    check_loss, get_type_counts,
)


class TzaarEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "tzaar",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "current_player": 0,
            "phase": "config",
            "sub_phase": None,
            "is_opening_move": True,
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

        if kind == "set_setup":
            return self._apply_set_setup(state, player_idx, action)
        elif kind == "capture":
            return self._apply_capture(state, player_idx, action)
        elif kind == "stack":
            return self._apply_stack(state, player_idx, action)
        elif kind == "pass":
            return self._apply_pass(state, player_idx)
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
            desc = "Select board setup"
        elif phase == "play":
            sub = state.get("sub_phase")
            if sub == "first_action":
                desc = f"{player_name} — must capture (1st action)"
            elif sub == "second_action":
                desc = f"{player_name} — capture, stack, or pass (2nd action)"
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
            {"kind": "set_setup", "setup": "random"},
            {"kind": "set_setup", "setup": "fixed"},
        ]

    def _apply_set_setup(self, state, player_idx, action):
        if state["phase"] != "config":
            raise ValueError("Not in config phase")
        if player_idx != 0:
            raise ValueError("Only the host can set setup")

        setup = action.get("setup")
        if setup not in ("random", "fixed"):
            raise ValueError("Setup must be 'random' or 'fixed'")

        if setup == "random":
            setup_random(state["board"])
        else:
            setup_fixed(state["board"])

        state["phase"] = "play"
        state["sub_phase"] = "first_action"
        state["current_player"] = 0  # White goes first
        state["is_opening_move"] = True

        setup_name = "Random" if setup == "random" else "Fixed"
        log = [f"{setup_name} setup. White opens with a single capture."]
        return ActionResult(state, log=log)

    # ── Play phase: valid actions ────────────────────────

    def _valid_play_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []

        sub = state.get("sub_phase")
        player_color = state["players"][player_idx]["color"]

        if sub == "first_action":
            # Must capture
            captures = find_captures(state["board"], player_color)
            return [{"kind": "capture", "from": c["from"], "to": c["to"]} for c in captures]

        elif sub == "second_action":
            actions = []
            # Can capture
            captures = find_captures(state["board"], player_color)
            for c in captures:
                actions.append({"kind": "capture", "from": c["from"], "to": c["to"]})
            # Can stack
            stacks = find_stacks(state["board"], player_color)
            for s in stacks:
                actions.append({"kind": "stack", "from": s["from"], "to": s["to"]})
            # Can always pass
            actions.append({"kind": "pass"})
            return actions

        return []

    # ── Play phase: apply actions ────────────────────────

    def _apply_capture(self, state, player_idx, action):
        if state["phase"] != "play":
            raise ValueError("Not in play phase")
        sub = state.get("sub_phase")
        if sub not in ("first_action", "second_action"):
            raise ValueError("Cannot capture now")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        from_key = action.get("from")
        to_key = action.get("to")
        if not from_key or not to_key:
            raise ValueError("Missing from or to")

        board = state["board"]
        attacker = board.get(from_key)
        target = board.get(to_key)
        player = state["players"][player_idx]
        player_color = player["color"]
        opp_color = "black" if player_color == "white" else "white"

        if not attacker or attacker["color"] != player_color:
            raise ValueError("No piece of yours at source")
        if not target or target["color"] != opp_color:
            raise ValueError("No opponent piece at destination")
        if attacker["height"] < target["height"]:
            raise ValueError("Your piece is not strong enough")

        # Validate straight-line movement to first occupied space
        self._validate_line_move(board, from_key, to_key)

        # Execute capture
        board[to_key] = attacker
        board[from_key] = None

        log = [f"{player['name']} captured at {to_key} (height {attacker['height']} vs {target['height']})."]

        # Check win: did opponent lose a type?
        if check_loss(board, opp_color):
            return self._end_game_winner(state, player_idx, log)

        # Advance phase
        if sub == "first_action":
            if state["is_opening_move"]:
                # White's first turn — only one action
                state["is_opening_move"] = False
                return self._advance_turn(state, log)
            else:
                state["sub_phase"] = "second_action"
                return ActionResult(state, log=log)
        else:
            # second_action capture — turn is done
            return self._advance_turn(state, log)

    def _apply_stack(self, state, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "second_action":
            raise ValueError("Can only stack as second action")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        from_key = action.get("from")
        to_key = action.get("to")
        if not from_key or not to_key:
            raise ValueError("Missing from or to")

        board = state["board"]
        mover = board.get(from_key)
        base = board.get(to_key)
        player = state["players"][player_idx]
        player_color = player["color"]

        if not mover or mover["color"] != player_color:
            raise ValueError("No piece of yours at source")
        if not base or base["color"] != player_color:
            raise ValueError("No piece of yours at destination")

        self._validate_line_move(board, from_key, to_key)

        # Stack: mover goes on top of base
        board[to_key] = {
            "color": player_color,
            "type": mover["type"],  # top piece determines type
            "height": mover["height"] + base["height"],
        }
        board[from_key] = None

        log = [f"{player['name']} stacked at {to_key} (now height {board[to_key]['height']})."]

        return self._advance_turn(state, log)

    def _apply_pass(self, state, player_idx):
        if state["phase"] != "play" or state.get("sub_phase") != "second_action":
            raise ValueError("Can only pass as second action")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        player = state["players"][player_idx]
        log = [f"{player['name']} passed their second action."]

        return self._advance_turn(state, log)

    # ── Movement validation ──────────────────────────────

    def _validate_line_move(self, board, from_key, to_key):
        """Validate that to_key is the first occupied space in a straight line from from_key."""
        from server.tzaar.state import AXIAL_DIRS
        fq, fr = parse_hex(from_key)
        tq, tr = parse_hex(to_key)

        for dq, dr in AXIAL_DIRS:
            target = find_line_target(board, from_key, dq, dr)
            if target == to_key:
                return  # Valid

        raise ValueError("Destination is not reachable in a straight line")

    # ── Turn advancement ─────────────────────────────────

    def _advance_turn(self, state, log):
        state["current_player"] = 1 - state["current_player"]
        state["sub_phase"] = "first_action"

        # Check if the new current player can capture (mandatory first action)
        player_color = state["players"][state["current_player"]]["color"]
        captures = find_captures(state["board"], player_color)

        if not captures:
            # Can't capture → loses
            winner_idx = 1 - state["current_player"]
            player_name = state["players"][state["current_player"]]["name"]
            log.append(f"{player_name} has no valid captures — loses!")
            return self._end_game_winner(state, winner_idx, log)

        return ActionResult(state, log=log)

    # ── Game end ─────────────────────────────────────────

    def _end_game_winner(self, state, winner_idx, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None
        state["winner"] = state["players"][winner_idx]["player_id"]
        p = state["players"][winner_idx]
        log.append(f"{p['name']} wins!")
        return ActionResult(state, log=log, game_over=True)

    # ── Helpers ──────────────────────────────────────────

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
