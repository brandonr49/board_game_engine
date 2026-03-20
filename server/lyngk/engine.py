"""LYNGK game engine — GameEngine subclass."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.lyngk.state import (
    ACTIVE_COLORS, JOKER_COLOR, MAX_CLAIMS_PER_PLAYER,
    hex_key, parse_hex, generate_board, create_player,
    setup_random, get_stack_top, find_valid_moves,
    can_stack_on, can_move, is_moveable_by, is_complete_stack,
)


class LyngkEngine(GameEngine):
    player_count_range = (2, 2)

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        board = generate_board()
        setup_random(board)

        return {
            "game": "lyngk",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": board,
            "claims": {"white": [], "black": []},
            "scores": [0, 0],
            "current_player": 0,
            "phase": "play",
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
        if player_idx != state["current_player"]:
            return []

        player_color = state["players"][player_idx]["color"]
        actions = []

        # Claim color actions (before move, max 2 per player)
        my_claims = state["claims"].get(player_color, [])
        if len(my_claims) < MAX_CLAIMS_PER_PLAYER:
            opp_color = "black" if player_color == "white" else "white"
            opp_claims = state["claims"].get(opp_color, [])
            for color in ACTIVE_COLORS:
                if color not in my_claims and color not in opp_claims:
                    actions.append({"kind": "claim_color", "color": color})

        # Move actions
        moves = find_valid_moves(state["board"], state["claims"], player_color)
        for m in moves:
            actions.append({"kind": "move", "from": m["from"], "to": m["to"]})

        # Pass if no moves (but claims still possible)
        if not moves:
            actions.append({"kind": "pass"})

        return actions

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        kind = action.get("kind")
        player_idx = self._player_index(state, player_id)
        if player_idx is None:
            raise ValueError("Unknown player")
        if state["game_over"]:
            raise ValueError("Game is over")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        if kind == "claim_color":
            return self._apply_claim(state, player_idx, action)
        elif kind == "move":
            return self._apply_move(state, player_idx, action)
        elif kind == "pass":
            return self._apply_pass(state, player_idx)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        cp = state["current_player"]
        name = state["players"][cp]["name"]
        return {
            "phase": state["phase"],
            "description": f"{name}'s turn",
            "current_player_name": name,
        }

    # ── Actions ──────────────────────────────────────────

    def _apply_claim(self, state, player_idx, action):
        color = action.get("color")
        if color not in ACTIVE_COLORS:
            raise ValueError("Invalid color")

        player = state["players"][player_idx]
        pc = player["color"]
        my_claims = state["claims"][pc]

        if len(my_claims) >= MAX_CLAIMS_PER_PLAYER:
            raise ValueError("Already claimed 2 colors")

        opp_pc = "black" if pc == "white" else "white"
        if color in state["claims"][opp_pc]:
            raise ValueError("Color already claimed by opponent")
        if color in my_claims:
            raise ValueError("Already claimed this color")

        my_claims.append(color)

        log = [f"{player['name']} claimed {color}!"]
        # Claiming doesn't end the turn — player still needs to move
        return ActionResult(state, log=log)

    def _apply_move(self, state, player_idx, action):
        from_key = action.get("from")
        to_key = action.get("to")

        if not from_key or not to_key:
            raise ValueError("Missing from or to")

        board = state["board"]
        if from_key not in board or to_key not in board:
            raise ValueError("Invalid position")

        from_stack = board[from_key]
        to_stack = board[to_key]

        if not from_stack:
            raise ValueError("No pieces at source")
        if not to_stack:
            raise ValueError("No pieces at destination")

        player = state["players"][player_idx]
        pc = player["color"]

        if not is_moveable_by(from_stack, state["claims"], pc):
            raise ValueError("Cannot move this piece/stack")

        top = get_stack_top(from_stack)
        if not can_stack_on(from_stack, to_stack):
            raise ValueError("Invalid stacking — colors conflict or too tall")
        if not can_move(from_stack, to_stack, top, state["claims"], pc):
            raise ValueError("Movement restricted for this piece type")

        # Execute move
        new_stack = to_stack + from_stack
        board[to_key] = new_stack
        board[from_key] = []

        log = [f"{player['name']} moved from {from_key} to {to_key} (height {len(new_stack)})."]

        # Check for completed 5-stack
        if is_complete_stack(new_stack):
            stack_top = get_stack_top(new_stack)
            # Is the top color claimed by current player?
            if stack_top in state["claims"].get(pc, []):
                state["scores"][player_idx] += 1
                board[to_key] = []  # Remove from board
                log.append(f"{player['name']} completed a 5-stack with {stack_top} on top! ({state['scores'][player_idx]} points)")
            else:
                log.append(f"5-stack completed with neutral/opponent color on top — remains as obstacle.")

        # Check game end
        return self._check_end_and_advance(state, player_idx, log)

    def _apply_pass(self, state, player_idx):
        player = state["players"][player_idx]
        pc = player["color"]

        # Verify no valid moves
        moves = find_valid_moves(state["board"], state["claims"], pc)
        if moves:
            raise ValueError("You have valid moves — cannot pass")

        log = [f"{player['name']} passed (no valid moves)."]
        return self._check_end_and_advance(state, player_idx, log)

    # ── End detection ────────────────────────────────────

    def _check_end_and_advance(self, state, player_idx, log):
        # Advance turn
        state["current_player"] = 1 - state["current_player"]
        next_pc = state["players"][state["current_player"]]["color"]

        # Check if next player has moves
        next_moves = find_valid_moves(state["board"], state["claims"], next_pc)
        if not next_moves:
            # Check if original player also has no moves
            orig_pc = state["players"][player_idx]["color"]
            orig_moves = find_valid_moves(state["board"], state["claims"], orig_pc)
            if not orig_moves:
                return self._end_game(state, log)
            else:
                # Skip back to original player
                state["current_player"] = player_idx
                next_name = state["players"][1 - player_idx]["name"]
                log.append(f"{next_name} has no valid moves — skipped.")

        return ActionResult(state, log=log)

    def _end_game(self, state, log):
        state["game_over"] = True
        state["phase"] = "game_over"

        s0, s1 = state["scores"]
        p0, p1 = state["players"]

        log.append(f"Game over! {p0['name']}: {s0} stacks, {p1['name']}: {s1} stacks.")

        if s0 > s1:
            state["winner"] = p0["player_id"]
            log.append(f"{p0['name']} wins!")
        elif s1 > s0:
            state["winner"] = p1["player_id"]
            log.append(f"{p1['name']} wins!")
        else:
            # Tiebreaker: count stack heights on board
            state["winner"] = None
            log.append("Draw!")

        return ActionResult(state, log=log, game_over=True)

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
