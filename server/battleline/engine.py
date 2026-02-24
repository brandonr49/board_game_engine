"""
Battle Line — game engine implementation.

Implements the GameEngine interface as a pure state machine.
All state is a plain dict. No side effects, no networking.

Phase machine:
  play_card → [tactic sub-phases] → claim_flags → draw_card → next player
"""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.battleline.state import (
    create_initial_state, check_win_condition, NUM_FLAGS,
)
from server.battleline.formations import can_claim_flag, best_formation


class BattleLineEngine(GameEngine):

    player_count_range = (2, 2)

    # ── Setup ─────────────────────────────────────────────────────────

    def initial_state(self, player_ids, player_names):
        if len(player_ids) != 2:
            raise ValueError("Battle Line requires exactly 2 players")
        return create_initial_state(player_ids, player_names)

    # ── Views ─────────────────────────────────────────────────────────

    def get_player_view(self, state, player_id):
        """Return state with opponent's hand and deck contents hidden."""
        view = deepcopy(state)
        player_idx = self._player_index(state, player_id)
        opponent_idx = 1 - player_idx

        # Hide opponent hand — show card types only (troop vs tactics)
        opp_hand = view["players"][opponent_idx]["hand"]
        view["players"][opponent_idx]["hand"] = [{"type": card["type"]} for card in opp_hand]

        # Hide deck contents — show sizes only
        view["troop_deck"] = len(view["troop_deck"])
        view["tactics_deck"] = len(view["tactics_deck"])

        # Remove internal log from view (server broadcasts separately)
        view.pop("log", None)

        return view

    def get_valid_actions(self, state, player_id):
        player_idx = self._player_index(state, player_id)
        if state["winner"] is not None:
            return []
        if state["current_player"] != player_idx:
            return []

        phase = state["phase"]
        sub = state["sub_phase"]

        if phase == "play_card":
            actions = self._valid_play_actions(state, player_idx)
        elif phase == "claim_flags":
            actions = self._valid_claim_actions(state, player_idx)
        elif phase == "draw_card":
            actions = self._valid_draw_actions(state)
        elif sub == "scout_draw":
            actions = self._valid_scout_draw_actions(state)
        elif sub == "scout_return":
            actions = self._valid_scout_return_actions(state, player_idx)
        elif sub == "redeploy_pick":
            actions = self._valid_redeploy_pick_actions(state, player_idx)
        elif sub == "redeploy_place":
            actions = self._valid_redeploy_place_actions(state, player_idx)
        elif sub == "deserter_pick":
            actions = self._valid_deserter_pick_actions(state, player_idx)
        elif sub == "traitor_pick":
            actions = self._valid_traitor_pick_actions(state, player_idx)
        elif sub == "traitor_place":
            actions = self._valid_traitor_place_actions(state, player_idx)
        else:
            actions = []

        actions.append({"kind": "toggle_auto_claim"})
        return actions

    def get_waiting_for(self, state):
        if state["winner"] is not None:
            return []
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        sub = state["sub_phase"]
        current = state["players"][state["current_player"]]["name"]

        desc_map = {
            "play_card": f"{current}: Play a card",
            "claim_flags": f"{current}: Claim flags or done",
            "draw_card": f"{current}: Draw a card",
        }
        sub_desc_map = {
            "scout_draw": f"{current}: Scout — draw cards",
            "scout_return": f"{current}: Scout — return cards",
            "redeploy_pick": f"{current}: Redeploy — pick a card",
            "redeploy_place": f"{current}: Redeploy — place card",
            "deserter_pick": f"{current}: Deserter — pick enemy card",
            "traitor_pick": f"{current}: Traitor — pick enemy troop",
            "traitor_place": f"{current}: Traitor — place stolen troop",
        }

        description = sub_desc_map.get(sub) or desc_map.get(phase, phase)

        return {
            "phase": sub or phase,
            "turn": state["turn_number"],
            "current_player": current,
            "description": description,
        }

    # ── Action Dispatch ───────────────────────────────────────────────

    def apply_action(self, state, player_id, action):
        player_idx = self._player_index(state, player_id)
        if state["winner"] is not None:
            raise ValueError("Game is over")
        if state["current_player"] != player_idx:
            raise ValueError("Not your turn")

        state = deepcopy(state)
        kind = action.get("kind")

        # Reset consecutive pass counter when a card is actually played
        play_actions = (
            "play_troop", "play_morale_tactic", "play_environment",
            "play_scout", "play_redeploy", "play_deserter", "play_traitor",
        )
        if kind in play_actions:
            state["consecutive_passes"] = 0

        # Toggle auto-claim: valid at any point during the active player's turn
        if kind == "toggle_auto_claim":
            state["auto_claim"] = not state.get("auto_claim", True)
            mode = "on" if state["auto_claim"] else "off"
            return ActionResult(new_state=state, log=[f"Auto-claim turned {mode}"], game_over=False)

        phase = state["phase"]
        sub = state["sub_phase"]
        log = []

        # ── Play Card Phase ───────────────────────────────────────
        if phase == "play_card":
            if kind == "play_troop":
                log = self._do_play_troop(state, player_idx, action)
            elif kind == "play_morale_tactic":
                log = self._do_play_morale_tactic(state, player_idx, action)
            elif kind == "play_environment":
                log = self._do_play_environment(state, player_idx, action)
            elif kind == "play_scout":
                log = self._do_play_scout(state, player_idx, action)
            elif kind == "play_redeploy":
                log = self._do_play_redeploy(state, player_idx, action)
            elif kind == "play_deserter":
                log = self._do_play_deserter(state, player_idx, action)
            elif kind == "play_traitor":
                log = self._do_play_traitor(state, player_idx, action)
            elif kind == "pass":
                log = self._do_pass(state, player_idx)
            else:
                raise ValueError(f"Invalid action kind for play_card: {kind}")

        # ── Claim Flags Phase ─────────────────────────────────────
        elif phase == "claim_flags":
            if kind == "claim_flag":
                log = self._do_claim_flag(state, player_idx, action)
            elif kind == "done_claiming":
                log = self._do_done_claiming(state, player_idx)
            else:
                raise ValueError(f"Invalid action kind for claim_flags: {kind}")

        # ── Draw Card Phase ───────────────────────────────────────
        elif phase == "draw_card":
            if kind == "draw_card":
                log = self._do_draw_card(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for draw_card: {kind}")

        # ── Sub-phases (tactics) ──────────────────────────────────
        elif sub == "scout_draw":
            if kind == "scout_draw_card":
                log = self._do_scout_draw(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for scout_draw: {kind}")

        elif sub == "scout_return":
            if kind == "scout_return_card":
                log = self._do_scout_return(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for scout_return: {kind}")

        elif sub == "redeploy_pick":
            if kind == "redeploy_pick":
                log = self._do_redeploy_pick(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for redeploy_pick: {kind}")

        elif sub == "redeploy_place":
            if kind in ("redeploy_place_to_flag", "redeploy_discard"):
                log = self._do_redeploy_place(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for redeploy_place: {kind}")

        elif sub == "deserter_pick":
            if kind == "deserter_pick":
                log = self._do_deserter_pick(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for deserter_pick: {kind}")

        elif sub == "traitor_pick":
            if kind == "traitor_pick":
                log = self._do_traitor_pick(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for traitor_pick: {kind}")

        elif sub == "traitor_place":
            if kind == "traitor_place":
                log = self._do_traitor_place(state, player_idx, action)
            else:
                raise ValueError(f"Invalid action kind for traitor_place: {kind}")

        else:
            raise ValueError(f"Invalid phase/sub_phase: {phase}/{sub}")

        # Check win condition (draw may already be set by consecutive passes)
        game_over = False
        if state["winner"] == "draw":
            game_over = True
        else:
            winner = check_win_condition(state)
            if winner is not None:
                state["winner"] = winner
                game_over = True
                log.append(f"{state['players'][winner]['name']} wins!")

        return ActionResult(new_state=state, log=log, game_over=game_over)

    # ── Valid Action Generators ───────────────────────────────────────

    def _valid_play_actions(self, state, player_idx):
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]
        actions = []

        # Available flag indices for placing cards
        available_flags = []
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            required = 4 if "mud" in flag["environment"] else 3
            if len(flag["slots"][player_idx]) < required:
                available_flags.append(fi)

        can_play_tactic = player["tactics_played"] <= opponent["tactics_played"]

        for ci, card in enumerate(hand):
            if card["type"] == "troop":
                for fi in available_flags:
                    actions.append({"kind": "play_troop", "card_index": ci, "flag_index": fi})
            elif card["type"] == "tactics":
                if not can_play_tactic:
                    continue
                subtype = card.get("subtype")
                card_id = card.get("id")

                if subtype in ("leader", "morale"):
                    # Leaders: check 1-per-player limit
                    if subtype == "leader" and player["has_leader_on_board"]:
                        continue
                    for fi in available_flags:
                        actions.append({"kind": "play_morale_tactic", "card_index": ci, "flag_index": fi})

                elif subtype == "environment":
                    for fi in range(NUM_FLAGS):
                        flag = state["flags"][fi]
                        if flag["claimed_by"] is not None:
                            continue
                        # Can't duplicate same environment on a flag
                        if card_id in flag["environment"]:
                            continue
                        actions.append({"kind": "play_environment", "card_index": ci, "flag_index": fi})

                elif card_id == "scout":
                    # Scout needs at least one deck to draw from
                    if state["troop_deck"] or state["tactics_deck"]:
                        actions.append({"kind": "play_scout", "card_index": ci})

                elif card_id == "redeploy":
                    # Need at least one own card on an unclaimed flag
                    if self._has_own_cards_on_unclaimed_flags(state, player_idx):
                        actions.append({"kind": "play_redeploy", "card_index": ci})

                elif card_id == "deserter":
                    # Need at least one opponent card on an unclaimed flag
                    if self._has_cards_on_unclaimed_flags(state, 1 - player_idx):
                        actions.append({"kind": "play_deserter", "card_index": ci})

                elif card_id == "traitor":
                    # Need at least one opponent TROOP on an unclaimed flag
                    if self._has_troops_on_unclaimed_flags(state, 1 - player_idx):
                        actions.append({"kind": "play_traitor", "card_index": ci})

        # Pass: allowed if no troop cards in hand OR all flag slots full
        has_troops = any(c["type"] == "troop" for c in hand)
        if not has_troops or not available_flags:
            actions.append({"kind": "pass"})

        return actions

    def _valid_claim_actions(self, state, player_idx):
        actions = []
        for fi in range(NUM_FLAGS):
            if can_claim_flag(state, player_idx, fi):
                actions.append({"kind": "claim_flag", "flag_index": fi})
        actions.append({"kind": "done_claiming"})
        return actions

    def _valid_draw_actions(self, state):
        actions = []
        if state["troop_deck"]:
            actions.append({"kind": "draw_card", "deck": "troop"})
        if state["tactics_deck"]:
            actions.append({"kind": "draw_card", "deck": "tactics"})
        return actions

    def _valid_scout_draw_actions(self, state):
        actions = []
        if state["troop_deck"]:
            actions.append({"kind": "scout_draw_card", "deck": "troop"})
        if state["tactics_deck"]:
            actions.append({"kind": "scout_draw_card", "deck": "tactics"})
        return actions

    def _valid_scout_return_actions(self, state, player_idx):
        hand = state["players"][player_idx]["hand"]
        actions = []
        for ci, card in enumerate(hand):
            if card["type"] == "troop":
                actions.append({"kind": "scout_return_card", "card_index": ci, "deck": "troop"})
            elif card["type"] == "tactics":
                actions.append({"kind": "scout_return_card", "card_index": ci, "deck": "tactics"})
        return actions

    def _valid_redeploy_pick_actions(self, state, player_idx):
        actions = []
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            for ci, card in enumerate(flag["slots"][player_idx]):
                # Can redeploy troop or morale tactics
                if card["type"] == "troop" or card.get("subtype") in ("leader", "morale"):
                    actions.append({"kind": "redeploy_pick", "flag_index": fi, "card_index_at_flag": ci})
        return actions

    def _valid_redeploy_place_actions(self, state, player_idx):
        actions = [{"kind": "redeploy_discard"}]
        rs = state["redeploy_state"]
        from_flag = rs["from_flag"]
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            if fi == from_flag:
                continue
            required = 4 if "mud" in flag["environment"] else 3
            if len(flag["slots"][player_idx]) < required:
                actions.append({"kind": "redeploy_place_to_flag", "flag_index": fi})
        return actions

    def _valid_deserter_pick_actions(self, state, player_idx):
        opponent = 1 - player_idx
        actions = []
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            for ci, card in enumerate(flag["slots"][opponent]):
                # Deserter can target troop or morale tactics
                if card["type"] == "troop" or card.get("subtype") in ("leader", "morale"):
                    actions.append({"kind": "deserter_pick", "flag_index": fi, "card_index_at_flag": ci})
        return actions

    def _valid_traitor_pick_actions(self, state, player_idx):
        opponent = 1 - player_idx
        actions = []
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            for ci, card in enumerate(flag["slots"][opponent]):
                # Traitor can only steal troop cards
                if card["type"] == "troop":
                    actions.append({"kind": "traitor_pick", "flag_index": fi, "card_index_at_flag": ci})
        return actions

    def _valid_traitor_place_actions(self, state, player_idx):
        actions = []
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is not None:
                continue
            required = 4 if "mud" in flag["environment"] else 3
            if len(flag["slots"][player_idx]) < required:
                actions.append({"kind": "traitor_place", "flag_index": fi})
        return actions

    # ── Action Implementations ────────────────────────────────────────

    def _do_play_troop(self, state, player_idx, action):
        ci = action["card_index"]
        fi = action["flag_index"]
        player = state["players"][player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card["type"] != "troop":
            raise ValueError("Selected card is not a troop")

        self._validate_flag_placement(state, player_idx, fi)

        # Play the card
        hand.pop(ci)
        state["flags"][fi]["slots"][player_idx].append(card)
        self._check_completion(state, player_idx, fi)

        log = [f"{player['name']} plays {card['color']} {card['value']} on flag {fi + 1}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    def _do_play_morale_tactic(self, state, player_idx, action):
        ci = action["card_index"]
        fi = action["flag_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card["type"] != "tactics" or card.get("subtype") not in ("leader", "morale"):
            raise ValueError("Selected card is not a morale tactic")

        self._validate_tactics_limit(player, opponent)
        if card.get("subtype") == "leader" and player["has_leader_on_board"]:
            raise ValueError("You already have a leader on the board")

        self._validate_flag_placement(state, player_idx, fi)

        # Play the card
        hand.pop(ci)
        state["flags"][fi]["slots"][player_idx].append(card)
        player["tactics_played"] += 1
        if card.get("subtype") == "leader":
            player["has_leader_on_board"] = True
        self._check_completion(state, player_idx, fi)

        log = [f"{player['name']} plays {card['name']} on flag {fi + 1}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    def _do_play_environment(self, state, player_idx, action):
        ci = action["card_index"]
        fi = action["flag_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card["type"] != "tactics" or card.get("subtype") != "environment":
            raise ValueError("Selected card is not an environment tactic")

        self._validate_tactics_limit(player, opponent)

        flag = state["flags"][fi]
        if flag["claimed_by"] is not None:
            raise ValueError("Flag already claimed")
        if card["id"] in flag["environment"]:
            raise ValueError(f"{card['name']} already on this flag")

        # Play the card onto the flag's environment list
        hand.pop(ci)
        flag["environment"].append(card["id"])
        player["tactics_played"] += 1

        # Mud increases required cards from 3 to 4 — clear stale completions
        # and re-check both sides
        if card["id"] == "mud":
            for pidx in range(2):
                self._uncheck_completion(state, pidx, fi)

        log = [f"{player['name']} plays {card['name']} on flag {fi + 1}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    def _do_play_scout(self, state, player_idx, action):
        ci = action["card_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card.get("id") != "scout":
            raise ValueError("Selected card is not Scout")

        self._validate_tactics_limit(player, opponent)

        if not state["troop_deck"] and not state["tactics_deck"]:
            raise ValueError("No cards to draw")

        hand.pop(ci)
        player["tactics_played"] += 1
        state["discard"][player_idx].append(card)

        # Determine how many draws are available (up to 3)
        total_available = len(state["troop_deck"]) + len(state["tactics_deck"])
        draws = min(3, total_available)

        state["phase"] = "sub_phase"
        state["sub_phase"] = "scout_draw"
        state["scout_state"] = {"draws_remaining": draws, "returns_remaining": 2}
        state["skip_draw"] = True

        return [f"{player['name']} plays Scout"]

    def _do_play_redeploy(self, state, player_idx, action):
        ci = action["card_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card.get("id") != "redeploy":
            raise ValueError("Selected card is not Redeploy")

        self._validate_tactics_limit(player, opponent)

        if not self._has_own_cards_on_unclaimed_flags(state, player_idx):
            raise ValueError("No cards to redeploy")

        hand.pop(ci)
        player["tactics_played"] += 1
        state["discard"][player_idx].append(card)

        state["phase"] = "sub_phase"
        state["sub_phase"] = "redeploy_pick"

        return [f"{player['name']} plays Redeploy"]

    def _do_play_deserter(self, state, player_idx, action):
        ci = action["card_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card.get("id") != "deserter":
            raise ValueError("Selected card is not Deserter")

        self._validate_tactics_limit(player, opponent)

        if not self._has_cards_on_unclaimed_flags(state, 1 - player_idx):
            raise ValueError("No opponent cards to remove")

        hand.pop(ci)
        player["tactics_played"] += 1
        state["discard"][player_idx].append(card)

        state["phase"] = "sub_phase"
        state["sub_phase"] = "deserter_pick"

        return [f"{player['name']} plays Deserter"]

    def _do_play_traitor(self, state, player_idx, action):
        ci = action["card_index"]
        player = state["players"][player_idx]
        opponent = state["players"][1 - player_idx]
        hand = player["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]
        if card.get("id") != "traitor":
            raise ValueError("Selected card is not Traitor")

        self._validate_tactics_limit(player, opponent)

        if not self._has_troops_on_unclaimed_flags(state, 1 - player_idx):
            raise ValueError("No opponent troops to steal")

        hand.pop(ci)
        player["tactics_played"] += 1
        state["discard"][player_idx].append(card)

        state["phase"] = "sub_phase"
        state["sub_phase"] = "traitor_pick"

        return [f"{player['name']} plays Traitor"]

    def _do_pass(self, state, player_idx):
        player = state["players"][player_idx]
        hand = player["hand"]

        has_troops = any(c["type"] == "troop" for c in hand)
        has_open_flags = any(
            state["flags"][fi]["claimed_by"] is None
            and len(state["flags"][fi]["slots"][player_idx]) < (4 if "mud" in state["flags"][fi]["environment"] else 3)
            for fi in range(NUM_FLAGS)
        )

        if has_troops and has_open_flags:
            raise ValueError("You have troop cards and open flag slots — must play a card")

        state["consecutive_passes"] = state.get("consecutive_passes", 0) + 1
        log = [f"{player['name']} passes"]

        # Two consecutive passes = draw
        if state["consecutive_passes"] >= 2:
            state["winner"] = "draw"
            log.append("Both players passed consecutively — game is a draw")
            return log

        log += self._enter_claim_phase(state, player_idx)
        return log

    # ── Claim Flags ───────────────────────────────────────────────────

    def _enter_claim_phase(self, state, player_idx, skip_draw=False):
        """Either auto-claim provable flags or enter manual claim phase.

        If skip_draw is True (e.g. after Scout), bypass the draw phase entirely.
        """
        log = []
        if state.get("auto_claim", True):
            # Auto-claim all provable flags
            for fi in range(NUM_FLAGS):
                if can_claim_flag(state, player_idx, fi):
                    state["flags"][fi]["claimed_by"] = player_idx
                    name = state["players"][player_idx]["name"]
                    log.append(f"{name} claims flag {fi + 1}")
            if skip_draw:
                log += self._advance_turn(state)
            else:
                state["phase"] = "draw_card"
                if not state["troop_deck"] and not state["tactics_deck"]:
                    log += self._advance_turn(state)
        else:
            state["phase"] = "claim_flags"
            if skip_draw:
                state["skip_draw"] = True
        return log

    def _do_claim_flag(self, state, player_idx, action):
        fi = action["flag_index"]
        if fi < 0 or fi >= NUM_FLAGS:
            raise ValueError("Invalid flag index")

        if not can_claim_flag(state, player_idx, fi):
            raise ValueError("Cannot claim this flag")

        state["flags"][fi]["claimed_by"] = player_idx
        name = state["players"][player_idx]["name"]
        return [f"{name} claims flag {fi + 1}"]

    def _do_done_claiming(self, state, player_idx):
        # Skip draw phase if flagged (e.g. after Scout)
        if state.pop("skip_draw", False):
            return self._advance_turn(state)

        # Move to draw phase
        state["phase"] = "draw_card"

        # Auto-skip draw if both decks empty
        if not state["troop_deck"] and not state["tactics_deck"]:
            return self._advance_turn(state)

        return []

    # ── Draw Card ─────────────────────────────────────────────────────

    def _do_draw_card(self, state, player_idx, action):
        deck_name = action.get("deck")
        if deck_name not in ("troop", "tactics"):
            raise ValueError("Must specify deck: 'troop' or 'tactics'")

        deck_key = f"{deck_name}_deck"
        if not state[deck_key]:
            raise ValueError(f"{deck_name.title()} deck is empty")

        card = state[deck_key].pop()
        state["players"][player_idx]["hand"].append(card)

        log = self._advance_turn(state)
        return log

    # ── Scout Sub-phases ──────────────────────────────────────────────

    def _do_scout_draw(self, state, player_idx, action):
        deck_name = action.get("deck")
        if deck_name not in ("troop", "tactics"):
            raise ValueError("Must specify deck: 'troop' or 'tactics'")

        deck_key = f"{deck_name}_deck"
        if not state[deck_key]:
            raise ValueError(f"{deck_name.title()} deck is empty")

        card = state[deck_key].pop()
        state["players"][player_idx]["hand"].append(card)

        ss = state["scout_state"]
        ss["draws_remaining"] -= 1

        if ss["draws_remaining"] <= 0:
            state["sub_phase"] = "scout_return"
        # Also check if no more cards to draw
        elif not state["troop_deck"] and not state["tactics_deck"]:
            state["sub_phase"] = "scout_return"

        return []

    def _do_scout_return(self, state, player_idx, action):
        ci = action["card_index"]
        deck_target = action.get("deck")
        hand = state["players"][player_idx]["hand"]

        self._validate_card_index(hand, ci)
        card = hand[ci]

        # Validate deck target matches card type
        if card["type"] == "troop" and deck_target != "troop":
            raise ValueError("Troop cards must go to troop deck")
        if card["type"] == "tactics" and deck_target != "tactics":
            raise ValueError("Tactics cards must go to tactics deck")

        hand.pop(ci)
        deck_key = f"{deck_target}_deck"
        # Put on top of deck (end of list = top)
        state[deck_key].append(card)

        ss = state["scout_state"]
        ss["returns_remaining"] -= 1

        if ss["returns_remaining"] <= 0:
            state["scout_state"] = None
            state["sub_phase"] = None
            # Scout's draws replace the normal end-of-turn draw
            return self._enter_claim_phase(state, player_idx, skip_draw=True)

        return []

    # ── Redeploy Sub-phases ───────────────────────────────────────────

    def _do_redeploy_pick(self, state, player_idx, action):
        fi = action["flag_index"]
        ci = action["card_index_at_flag"]

        flag = state["flags"][fi]
        if flag["claimed_by"] is not None:
            raise ValueError("Flag already claimed")

        slots = flag["slots"][player_idx]
        if ci < 0 or ci >= len(slots):
            raise ValueError("Invalid card index at flag")

        card = slots[ci]
        if card["type"] != "troop" and card.get("subtype") not in ("leader", "morale"):
            raise ValueError("Can only redeploy troops or morale tactics")

        # Remove card from flag
        picked = slots.pop(ci)

        # Update completion status
        self._uncheck_completion(state, player_idx, fi)

        # Update leader tracking if needed
        if picked.get("subtype") == "leader":
            state["players"][player_idx]["has_leader_on_board"] = False

        state["redeploy_state"] = {"picked_card": picked, "from_flag": fi}
        state["sub_phase"] = "redeploy_place"

        return []

    def _do_redeploy_place(self, state, player_idx, action):
        rs = state["redeploy_state"]
        card = rs["picked_card"]

        if action["kind"] == "redeploy_discard":
            state["discard"][player_idx].append(card)
            log_msg = f"discards {self._card_name(card)}"
        else:
            fi = action["flag_index"]
            self._validate_flag_placement(state, player_idx, fi)
            if fi == rs["from_flag"]:
                raise ValueError("Cannot redeploy to the same flag")
            state["flags"][fi]["slots"][player_idx].append(card)
            if card.get("subtype") == "leader":
                state["players"][player_idx]["has_leader_on_board"] = True
            self._check_completion(state, player_idx, fi)
            log_msg = f"redeploys {self._card_name(card)} to flag {fi + 1}"

        state["redeploy_state"] = None
        state["sub_phase"] = None

        name = state["players"][player_idx]["name"]
        log = [f"{name} {log_msg}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    # ── Deserter Sub-phase ────────────────────────────────────────────

    def _do_deserter_pick(self, state, player_idx, action):
        fi = action["flag_index"]
        ci = action["card_index_at_flag"]
        opponent = 1 - player_idx

        flag = state["flags"][fi]
        if flag["claimed_by"] is not None:
            raise ValueError("Flag already claimed")

        slots = flag["slots"][opponent]
        if ci < 0 or ci >= len(slots):
            raise ValueError("Invalid card index at flag")

        card = slots[ci]
        if card["type"] != "troop" and card.get("subtype") not in ("leader", "morale"):
            raise ValueError("Can only desert troops or morale tactics")

        # Remove and discard
        removed = slots.pop(ci)
        state["discard"][opponent].append(removed)

        # Update completion and leader tracking
        self._uncheck_completion(state, opponent, fi)
        if removed.get("subtype") == "leader":
            state["players"][opponent]["has_leader_on_board"] = False

        state["sub_phase"] = None

        name = state["players"][player_idx]["name"]
        log = [f"{name} deserts {self._card_name(removed)} from flag {fi + 1}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    # ── Traitor Sub-phases ────────────────────────────────────────────

    def _do_traitor_pick(self, state, player_idx, action):
        fi = action["flag_index"]
        ci = action["card_index_at_flag"]
        opponent = 1 - player_idx

        flag = state["flags"][fi]
        if flag["claimed_by"] is not None:
            raise ValueError("Flag already claimed")

        slots = flag["slots"][opponent]
        if ci < 0 or ci >= len(slots):
            raise ValueError("Invalid card index at flag")

        card = slots[ci]
        if card["type"] != "troop":
            raise ValueError("Traitor can only steal troop cards")

        # Remove from opponent's side
        stolen = slots.pop(ci)
        self._uncheck_completion(state, opponent, fi)

        state["traitor_state"] = {"picked_card": stolen, "from_flag": fi}
        state["sub_phase"] = "traitor_place"

        name = state["players"][player_idx]["name"]
        return [f"{name} steals {self._card_name(stolen)} from flag {fi + 1}"]

    def _do_traitor_place(self, state, player_idx, action):
        fi = action["flag_index"]
        ts = state["traitor_state"]
        card = ts["picked_card"]

        self._validate_flag_placement(state, player_idx, fi)

        state["flags"][fi]["slots"][player_idx].append(card)
        self._check_completion(state, player_idx, fi)

        state["traitor_state"] = None
        state["sub_phase"] = None

        name = state["players"][player_idx]["name"]
        log = [f"{name} places stolen {self._card_name(card)} on flag {fi + 1}"]
        log += self._enter_claim_phase(state, player_idx)
        return log

    # ── Helpers ───────────────────────────────────────────────────────

    def _player_index(self, state, player_id):
        try:
            return state["player_ids"].index(player_id)
        except ValueError:
            raise ValueError(f"Player {player_id} not in this game")

    def _validate_card_index(self, hand, ci):
        if ci < 0 or ci >= len(hand):
            raise ValueError("Invalid card index")

    def _validate_flag_placement(self, state, player_idx, fi):
        if fi < 0 or fi >= NUM_FLAGS:
            raise ValueError("Invalid flag index")
        flag = state["flags"][fi]
        if flag["claimed_by"] is not None:
            raise ValueError("Flag already claimed")
        required = 4 if "mud" in flag["environment"] else 3
        if len(flag["slots"][player_idx]) >= required:
            raise ValueError("Flag side is full")

    def _validate_tactics_limit(self, player, opponent):
        if player["tactics_played"] > opponent["tactics_played"]:
            raise ValueError("Cannot play more tactics than opponent has played")

    def _check_completion(self, state, player_idx, flag_idx):
        """Record completion_turn when a player fills their side of a flag."""
        flag = state["flags"][flag_idx]
        required = 4 if "mud" in flag["environment"] else 3
        if len(flag["slots"][player_idx]) >= required and flag["completion_turn"][player_idx] is None:
            flag["completion_turn"][player_idx] = state["turn_number"]

    def _uncheck_completion(self, state, player_idx, flag_idx):
        """Clear completion_turn when a card is removed from a flag side."""
        flag = state["flags"][flag_idx]
        required = 4 if "mud" in flag["environment"] else 3
        if len(flag["slots"][player_idx]) < required:
            flag["completion_turn"][player_idx] = None

    def _advance_turn(self, state):
        """Switch to the next player's turn."""
        state["current_player"] = 1 - state["current_player"]
        state["turn_number"] += 1
        state["phase"] = "play_card"
        state["sub_phase"] = None
        state["skip_draw"] = False
        return []

    def _has_own_cards_on_unclaimed_flags(self, state, player_idx):
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is None and flag["slots"][player_idx]:
                return True
        return False

    def _has_cards_on_unclaimed_flags(self, state, player_idx):
        """Check if player has any cards (troop or morale) on unclaimed flags."""
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is None:
                for card in flag["slots"][player_idx]:
                    if card["type"] == "troop" or card.get("subtype") in ("leader", "morale"):
                        return True
        return False

    def _has_troops_on_unclaimed_flags(self, state, player_idx):
        """Check if player has any troop cards on unclaimed flags."""
        for fi in range(NUM_FLAGS):
            flag = state["flags"][fi]
            if flag["claimed_by"] is None:
                for card in flag["slots"][player_idx]:
                    if card["type"] == "troop":
                        return True
        return False

    def _card_name(self, card):
        if card["type"] == "troop":
            return f"{card['color']} {card['value']}"
        return card.get("name", card.get("id", "unknown"))
