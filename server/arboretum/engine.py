"""
Arboretum — game engine implementation.

Implements the GameEngine interface as a pure state machine.
All state is a plain dict. No side effects, no networking.

Phase machine:
  draw1 → draw2 → place → discard → (next player's draw1 or game end)
"""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.arboretum.state import (
    create_initial_state, get_valid_placements, pos_key, parse_key,
)
from server.arboretum.scoring import compute_final_scores


class ArboretumEngine(GameEngine):

    player_count_range = (2, 4)

    # ── Setup ─────────────────────────────────────────────────────────

    def initial_state(self, player_ids, player_names):
        if len(player_ids) < 2 or len(player_ids) > 4:
            raise ValueError("Arboretum requires 2-4 players")
        return create_initial_state(player_ids, player_names)

    # ── Views ─────────────────────────────────────────────────────────

    def get_player_view(self, state, player_id):
        """Return state with opponents' hands and draw pile hidden."""
        view = deepcopy(state)
        player_idx = self._player_index(state, player_id)

        # Hide other players' hands (show count only)
        for i, p in enumerate(view["players"]):
            if i != player_idx:
                p["hand"] = len(p["hand"])

        # Hide draw pile contents (show count only)
        view["draw_pile"] = len(view["draw_pile"])
        view["draw_pile_count"] = view["draw_pile"]

        return view

    def get_valid_actions(self, state, player_id):
        player_idx = self._player_index(state, player_id)
        if state["game_over"]:
            return []
        if state["current_player"] != player_idx:
            return []

        phase = state["phase"]
        player = state["players"][player_idx]

        if phase in ("draw1", "draw2"):
            return self._valid_draw_actions(state, player_idx)
        elif phase == "place":
            return self._valid_place_actions(state, player_idx)
        elif phase == "discard":
            return self._valid_discard_actions(state, player_idx)
        else:
            return []

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        current = state["players"][state["current_player"]]["name"]

        desc_map = {
            "draw1": f"{current}: Draw first card",
            "draw2": f"{current}: Draw second card",
            "place": f"{current}: Place a card",
            "discard": f"{current}: Discard a card",
        }

        return {
            "phase": phase,
            "turn": state["turn_number"],
            "current_player": current,
            "description": desc_map.get(phase, phase),
        }

    # ── Action Dispatch ───────────────────────────────────────────────

    def apply_action(self, state, player_id, action):
        player_idx = self._player_index(state, player_id)
        if state["game_over"]:
            raise ValueError("Game is over")
        if state["current_player"] != player_idx:
            raise ValueError("Not your turn")

        state = deepcopy(state)
        kind = action.get("kind")
        phase = state["phase"]
        log = []

        if phase in ("draw1", "draw2"):
            if kind != "draw_card":
                raise ValueError(f"Invalid action kind for {phase}: {kind}")
            log = self._do_draw_card(state, player_idx, action)

        elif phase == "place":
            if kind != "place_card":
                raise ValueError(f"Invalid action kind for place: {kind}")
            log = self._do_place_card(state, player_idx, action)

        elif phase == "discard":
            if kind != "discard_card":
                raise ValueError(f"Invalid action kind for discard: {kind}")
            log = self._do_discard_card(state, player_idx, action)

        else:
            raise ValueError(f"Invalid phase: {phase}")

        # Check game over
        game_over = state["game_over"]

        return ActionResult(new_state=state, log=log, game_over=game_over)

    # ── Valid Action Generators ───────────────────────────────────────

    def _valid_draw_actions(self, state, player_idx):
        actions = []

        # Draw from draw pile
        if state["draw_pile"]:
            actions.append({"kind": "draw_card", "source": "deck"})

        # Draw from any player's discard pile (including own)
        for pi, player in enumerate(state["players"]):
            if player["discard"]:
                actions.append({
                    "kind": "draw_card",
                    "source": "discard",
                    "player_index": pi,
                })

        return actions

    def _valid_place_actions(self, state, player_idx):
        """Return valid placement positions (not card×position combos)."""
        player = state["players"][player_idx]
        grid = player["grid"]
        valid_positions = get_valid_placements(grid)

        actions = []
        for row, col in valid_positions:
            actions.append({
                "kind": "place_card",
                "row": row,
                "col": col,
            })

        return actions

    def _valid_discard_actions(self, state, player_idx):
        player = state["players"][player_idx]
        actions = []
        for ci in range(len(player["hand"])):
            actions.append({"kind": "discard_card", "card_index": ci})
        return actions

    # ── Action Implementations ────────────────────────────────────────

    def _do_draw_card(self, state, player_idx, action):
        player = state["players"][player_idx]
        source = action.get("source")

        if source == "deck":
            if not state["draw_pile"]:
                raise ValueError("Draw pile is empty")
            card = state["draw_pile"].pop()
            player["hand"].append(card)
            state["draw_pile_count"] = len(state["draw_pile"])
            log_msg = f"{player['name']} draws from the deck"

        elif source == "discard":
            pi = action.get("player_index")
            if pi is None or pi < 0 or pi >= len(state["players"]):
                raise ValueError("Invalid player index for discard draw")
            target_player = state["players"][pi]
            if not target_player["discard"]:
                raise ValueError(f"{target_player['name']}'s discard pile is empty")
            # Take top card (last in list)
            card = target_player["discard"].pop()
            player["hand"].append(card)
            target_name = target_player["name"]
            if pi == player_idx:
                log_msg = f"{player['name']} draws from own discard"
            else:
                log_msg = f"{player['name']} draws from {target_name}'s discard"

        else:
            raise ValueError(f"Invalid draw source: {source}")

        # Advance phase
        ds = state["draw_state"]
        ds["cards_drawn"] += 1

        if state["phase"] == "draw1":
            ds["first_drawn_card"] = card
            # Check if draw2 is possible
            has_any_source = bool(state["draw_pile"])
            if not has_any_source:
                for p in state["players"]:
                    if p["discard"]:
                        has_any_source = True
                        break
            if has_any_source:
                state["phase"] = "draw2"
            else:
                # Skip draw2 if no sources available
                state["phase"] = "place"
        else:
            # draw2 complete
            state["phase"] = "place"

        return [log_msg]

    def _do_place_card(self, state, player_idx, action):
        ci = action.get("card_index")
        row = action.get("row")
        col = action.get("col")

        player = state["players"][player_idx]
        hand = player["hand"]

        if ci is None or ci < 0 or ci >= len(hand):
            raise ValueError("Invalid card index")

        grid = player["grid"]
        key = pos_key(row, col)

        # Validate position
        valid_positions = get_valid_placements(grid)
        if (row, col) not in valid_positions:
            raise ValueError(f"Invalid placement position: ({row}, {col})")

        if key in grid:
            raise ValueError("Position already occupied")

        # Place the card
        card = hand.pop(ci)
        grid[key] = card

        state["phase"] = "discard"
        species_name = self._species_display_name(state, card["species"])
        return [f"{player['name']} places {species_name} {card['value']} at ({row},{col})"]

    def _do_discard_card(self, state, player_idx, action):
        ci = action.get("card_index")
        player = state["players"][player_idx]
        hand = player["hand"]

        if ci is None or ci < 0 or ci >= len(hand):
            raise ValueError("Invalid card index")

        card = hand.pop(ci)
        player["discard"].append(card)

        species_name = self._species_display_name(state, card["species"])
        log = [f"{player['name']} discards {species_name} {card['value']}"]

        # Check if game should end (draw pile empty after discard)
        if not state["draw_pile"]:
            log += self._end_game(state)
        else:
            log += self._advance_turn(state)

        return log

    # ── Helpers ───────────────────────────────────────────────────────

    def _player_index(self, state, player_id):
        try:
            return state["player_ids"].index(player_id)
        except ValueError:
            raise ValueError(f"Player {player_id} not in this game")

    def _species_display_name(self, state, species_id):
        for s in state["active_species"]:
            if s["id"] == species_id:
                return s["name"]
        return species_id

    def _advance_turn(self, state):
        """Switch to the next player's turn."""
        state["current_player"] = (state["current_player"] + 1) % state["player_count"]
        state["turn_number"] += 1
        state["phase"] = "draw1"
        state["draw_state"] = {"cards_drawn": 0, "first_drawn_card": None}
        return []

    def _end_game(self, state):
        """Trigger end-of-game scoring."""
        scoring = compute_final_scores(state)
        state["scoring_results"] = scoring
        state["game_over"] = True

        # Determine winner
        winners = scoring["winners"]
        if len(winners) == 1:
            state["winner"] = winners[0]
            winner_name = state["players"][winners[0]]["name"]
            return [f"Game over! {winner_name} wins with {scoring['totals'][winners[0]]} points!"]
        else:
            state["winner"] = winners[0]  # First tied player for simplicity
            names = " and ".join(state["players"][w]["name"] for w in winners)
            score = scoring["totals"][winners[0]]
            return [f"Game over! {names} tie with {score} points!"]
