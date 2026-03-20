"""DVONN game engine — GameEngine subclass."""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.dvonn.state import (
    PIECES_PER_PLAYER, DVONN_PIECE_COUNT, TOTAL_SPACES,
    board_key, parse_key, generate_board, create_player,
    get_neighbors, get_line_destinations, is_straight_line,
    is_surrounded, find_connected_to_dvonn,
)


class DvonnEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "dvonn",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "current_player": 0,  # White starts placement
            "phase": "placement",
            "placement_sub_phase": "dvonn",  # "dvonn" then "colored"
            "pieces_placed": 0,
            "consecutive_passes": 0,
            "last_move": None,  # {"from": key, "to": key} for UI highlighting
            "last_removed": [],  # list of keys removed last turn
            "game_over": False,
            "winner": None,
        }

    def get_player_view(self, state, player_id):
        # DVONN is perfect information — no hidden state
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

        if state["phase"] == "placement":
            return self._valid_placement_actions(state, player_idx)
        elif state["phase"] == "movement":
            return self._valid_movement_actions(state, player_idx)
        return []

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        kind = action.get("kind")
        player_idx = self._player_index(state, player_id)
        if player_idx is None:
            raise ValueError("Unknown player")
        if state["game_over"]:
            raise ValueError("Game is over")

        if kind == "place_piece":
            return self._apply_place_piece(state, player_id, player_idx, action)
        elif kind == "move_stack":
            return self._apply_move_stack(state, player_id, player_idx, action)
        elif kind == "pass":
            return self._apply_pass(state, player_id, player_idx)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        cp = state["current_player"]
        player_name = state["players"][cp]["name"] if state["players"] else ""

        if phase == "placement":
            sub = state.get("placement_sub_phase", "dvonn")
            if sub == "dvonn":
                desc = f"{player_name} — place a DVONN piece"
            else:
                desc = f"{player_name} — place a piece"
        elif phase == "movement":
            desc = f"{player_name}'s turn — move a stack"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "placement_sub_phase": state.get("placement_sub_phase"),
            "pieces_placed": state.get("pieces_placed", 0),
            "description": desc,
            "current_player_name": player_name,
        }

    # ── Placement phase ──────────────────────────────────

    def _valid_placement_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []

        # All empty spaces are valid placement targets
        actions = []
        for key, space in state["board"].items():
            if len(space["stack"]) == 0:
                actions.append({"kind": "place_piece", "position": key})
        return actions

    def _apply_place_piece(self, state, player_id, player_idx, action):
        if state["phase"] != "placement":
            raise ValueError("Not in placement phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        position = action.get("position")
        if not position:
            raise ValueError("Missing position")
        if position not in state["board"]:
            raise ValueError("Invalid board position")

        space = state["board"][position]
        if len(space["stack"]) > 0:
            raise ValueError("Space is already occupied")

        player = state["players"][player_idx]
        sub = state["placement_sub_phase"]

        if sub == "dvonn":
            # Placing DVONN pieces
            if player["dvonn_to_place"] <= 0:
                raise ValueError("No DVONN pieces left to place")
            space["stack"].append("dvonn")
            player["dvonn_to_place"] -= 1
        else:
            # Placing colored pieces
            if player["pieces_to_place"] <= 0:
                raise ValueError("No pieces left to place")
            space["stack"].append(player["color"])
            player["pieces_to_place"] -= 1

        state["pieces_placed"] += 1
        player_name = player["name"]
        piece_type = "DVONN" if sub == "dvonn" else player["color"]
        log = [f"{player_name} placed a {piece_type} piece at {position}."]

        # Determine next player and phase transitions
        if sub == "dvonn":
            # DVONN placement order: White(0), Black(1), White(0)
            # pieces_placed: 1->switch to Black, 2->switch to White, 3->done with dvonn
            if state["pieces_placed"] >= DVONN_PIECE_COUNT:
                state["placement_sub_phase"] = "colored"
                # Black places first colored piece
                state["current_player"] = 1
                log.append("All DVONN pieces placed. Now place colored pieces.")
            else:
                state["current_player"] = 1 - state["current_player"]
        else:
            # Colored piece placement: alternate players
            if state["pieces_placed"] >= TOTAL_SPACES:
                # Board is full — transition to movement
                state["phase"] = "movement"
                state["placement_sub_phase"] = None
                state["current_player"] = 0  # White moves first
                log.append("Board is full! Movement phase begins.")
            else:
                state["current_player"] = 1 - state["current_player"]

        return ActionResult(state, log=log)

    # ── Movement phase ───────────────────────────────────

    def _valid_movement_actions(self, state, player_idx):
        if player_idx != state["current_player"]:
            return []

        board = state["board"]
        player_color = state["players"][player_idx]["color"]
        actions = []

        for key, space in board.items():
            stack = space["stack"]
            if not stack:
                continue
            # Must control the stack (top piece = player's color)
            if stack[-1] != player_color:
                continue
            row, col = parse_key(key)
            # Cannot move if surrounded on all 6 sides
            if is_surrounded(board, row, col):
                continue

            stack_height = len(stack)
            destinations = get_line_destinations(board, row, col, stack_height)
            for dest_row, dest_col in destinations:
                actions.append({
                    "kind": "move_stack",
                    "from": key,
                    "to": board_key(dest_row, dest_col),
                })

        if not actions:
            actions = [{"kind": "pass"}]

        return actions

    def _apply_move_stack(self, state, player_id, player_idx, action):
        if state["phase"] != "movement":
            raise ValueError("Not in movement phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        from_key = action.get("from")
        to_key = action.get("to")
        if not from_key or not to_key:
            raise ValueError("Missing from or to")

        board = state["board"]
        if from_key not in board or to_key not in board:
            raise ValueError("Invalid board position")

        from_space = board[from_key]
        to_space = board[to_key]
        stack = from_space["stack"]

        if not stack:
            raise ValueError("No stack at source")

        player_color = state["players"][player_idx]["color"]
        if stack[-1] != player_color:
            raise ValueError("You don't control this stack")

        from_row, from_col = parse_key(from_key)
        to_row, to_col = parse_key(to_key)

        # Surrounded check
        if is_surrounded(board, from_row, from_col):
            raise ValueError("Stack is surrounded and cannot move")

        # Straight line + distance check
        stack_height = len(stack)
        if not is_straight_line(from_row, from_col, to_row, to_col, stack_height):
            raise ValueError(
                f"Must move exactly {stack_height} spaces in a straight line"
            )

        # Destination must be occupied
        if not to_space["stack"]:
            raise ValueError("Destination must be occupied")

        # Execute move: place source stack on top of destination
        to_space["stack"].extend(stack)
        from_space["stack"] = []

        state["last_move"] = {"from": from_key, "to": to_key}
        state["consecutive_passes"] = 0

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} moved stack from {from_key} to {to_key} "
               f"(height {stack_height})."]

        # Remove disconnected pieces
        removed = self._remove_disconnected(state, log)
        state["last_removed"] = removed

        # Check game end
        return self._check_game_end_and_advance(state, log)

    def _apply_pass(self, state, player_id, player_idx):
        if state["phase"] != "movement":
            raise ValueError("Not in movement phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        # Verify no valid moves
        actions = self._valid_movement_actions(state, player_idx)
        has_real_moves = any(a["kind"] != "pass" for a in actions)
        if has_real_moves:
            raise ValueError("You have valid moves — cannot pass")

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} passed (no valid moves)."]

        state["consecutive_passes"] += 1
        state["last_move"] = None
        state["last_removed"] = []

        if state["consecutive_passes"] >= 2:
            return self._end_game(state, log)

        # Advance to next player
        state["current_player"] = 1 - state["current_player"]

        # If the next player also can't move, end the game
        next_actions = self._valid_movement_actions(state, state["current_player"])
        next_has_moves = any(a["kind"] != "pass" for a in next_actions)
        if not next_has_moves:
            state["consecutive_passes"] += 1
            next_name = state["players"][state["current_player"]]["name"]
            log.append(f"{next_name} also has no valid moves.")
            return self._end_game(state, log)

        return ActionResult(state, log=log)

    # ── Connectivity removal ─────────────────────────────

    def _remove_disconnected(self, state, log):
        """Remove all stacks not connected to a DVONN piece. Returns list of removed keys."""
        board = state["board"]
        connected = find_connected_to_dvonn(board)
        removed = []

        for key, space in board.items():
            if space["stack"] and key not in connected:
                pieces_count = len(space["stack"])
                removed.append(key)
                log.append(f"Removed disconnected stack at {key} ({pieces_count} pieces).")
                space["stack"] = []

        return removed

    # ── Turn advancement & game end ──────────────────────

    def _check_game_end_and_advance(self, state, log):
        """After a move, check if the game should end, otherwise advance turn."""
        # Check if either player can move
        white_can_move = self._player_can_move(state, 0)
        black_can_move = self._player_can_move(state, 1)

        if not white_can_move and not black_can_move:
            return self._end_game(state, log)

        # Advance to next player
        state["current_player"] = 1 - state["current_player"]

        # If next player can't move, they must pass — but let them do it explicitly
        # unless we just want to auto-advance
        return ActionResult(state, log=log)

    def _player_can_move(self, state, player_idx):
        """Check if a player has any valid moves (not counting pass)."""
        board = state["board"]
        player_color = state["players"][player_idx]["color"]

        for key, space in board.items():
            stack = space["stack"]
            if not stack or stack[-1] != player_color:
                continue
            row, col = parse_key(key)
            if is_surrounded(board, row, col):
                continue
            destinations = get_line_destinations(board, row, col, len(stack))
            if destinations:
                return True
        return False

    def _end_game(self, state, log):
        state["game_over"] = True
        state["phase"] = "game_over"

        # Count pieces controlled by each player
        scores = [0, 0]
        board = state["board"]
        for space in board.values():
            stack = space["stack"]
            if not stack:
                continue
            top = stack[-1]
            if top == "white":
                scores[0] += len(stack)
            elif top == "black":
                scores[1] += len(stack)
            # Stacks topped by "dvonn" are neutral — no one scores them

        p0 = state["players"][0]
        p1 = state["players"][1]

        log.append(f"Game over! {p0['name']} controls {scores[0]} pieces, "
                   f"{p1['name']} controls {scores[1]} pieces.")

        if scores[0] > scores[1]:
            state["winner"] = p0["player_id"]
            log.append(f"{p0['name']} wins!")
        elif scores[1] > scores[0]:
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
