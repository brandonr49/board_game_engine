"""
Lost Cities – Game Engine.

2-player card game. Each turn: play or discard a card, then draw a card.
Build ascending expedition columns. Game ends when draw pile is empty.
"""

from copy import deepcopy
from server.game_engine import GameEngine, ActionResult
from server.lostcities.state import (
    EXPEDITIONS, EXPEDITION_NAMES, HAND_SIZE,
    generate_deck, create_player, score_player, can_place_card,
)


class LostCitiesEngine(GameEngine):
    player_count_range = (2, 2)

    def initial_state(self, player_ids, player_names):
        deck = generate_deck()
        players = []
        for i, (pid, name) in enumerate(zip(player_ids, player_names)):
            p = create_player(i, pid, name)
            p["hand"] = deck[:HAND_SIZE]
            deck = deck[HAND_SIZE:]
            players.append(p)

        return {
            "game": "lostcities",
            "player_ids": player_ids,
            "player_count": 2,
            "players": players,
            "draw_pile": deck,
            "discard_piles": {exp: [] for exp in EXPEDITIONS},
            "current_player": 0,
            "phase": "play",  # "play" -> "draw" -> next player's "play"
            "last_discarded_expedition": None,  # can't draw from this
            "game_over": False,
            "winner": None,
            "scoring": None,
        }

    # ── Views ─────────────────────────────────────────────────────

    def get_player_view(self, state, player_id):
        view = deepcopy(state)
        view["your_player_id"] = player_id
        view["draw_pile_count"] = len(state["draw_pile"])
        del view["draw_pile"]

        # Show discard pile top cards only (plus count)
        for exp in EXPEDITIONS:
            pile = view["discard_piles"][exp]
            view["discard_piles"][exp] = {
                "top": pile[-1] if pile else None,
                "count": len(pile),
            }

        # Hide opponent's hand
        for p in view["players"]:
            if p["player_id"] != player_id:
                p["hand"] = len(p["hand"])

        view["valid_actions"] = self.get_valid_actions(state, player_id)
        return view

    def get_phase_info(self, state):
        if state["game_over"]:
            return {"phase": "game_over", "description": "Game over!"}
        p = state["players"][state["current_player"]]
        if state["phase"] == "play":
            return {
                "phase": "play",
                "description": f"{p['name']}: Play or discard a card",
                "current_player": p["name"],
            }
        else:
            return {
                "phase": "draw",
                "description": f"{p['name']}: Draw a card",
                "current_player": p["name"],
            }

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        return [state["player_ids"][state["current_player"]]]

    # ── Valid Actions ─────────────────────────────────────────────

    def get_valid_actions(self, state, player_id):
        if state["game_over"]:
            return []
        idx = next((i for i, p in enumerate(state["players"])
                     if p["player_id"] == player_id), None)
        if idx is None or idx != state["current_player"]:
            return []

        player = state["players"][idx]
        actions = []

        if state["phase"] == "play":
            for card in player["hand"]:
                # Option 1: play to expedition
                if can_place_card(player["expeditions"][card["expedition"]], card):
                    actions.append({
                        "kind": "play",
                        "card_id": card["id"],
                        "expedition": card["expedition"],
                    })
                # Option 2: discard
                actions.append({
                    "kind": "discard",
                    "card_id": card["id"],
                    "expedition": card["expedition"],
                })

        elif state["phase"] == "draw":
            # Draw from draw pile
            if state["draw_pile"]:
                actions.append({"kind": "draw", "source": "draw_pile"})
            # Draw from any non-empty discard pile (except last discarded)
            for exp in EXPEDITIONS:
                if (state["discard_piles"][exp]
                        and exp != state.get("last_discarded_expedition")):
                    actions.append({
                        "kind": "draw",
                        "source": "discard",
                        "expedition": exp,
                    })

        return actions

    # ── Apply Action ──────────────────────────────────────────────

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        idx = next((i for i, p in enumerate(state["players"])
                     if p["player_id"] == player_id), None)
        if idx is None or idx != state["current_player"]:
            raise ValueError("Not your turn")

        kind = action.get("kind")
        if kind == "play":
            return self._apply_play(state, idx, action)
        elif kind == "discard":
            return self._apply_discard(state, idx, action)
        elif kind == "draw":
            return self._apply_draw(state, idx, action)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def _apply_play(self, state, idx, action):
        if state["phase"] != "play":
            raise ValueError("Not in play phase")

        player = state["players"][idx]
        card_id = action.get("card_id")
        card = self._remove_card_from_hand(player, card_id)
        exp = card["expedition"]

        if not can_place_card(player["expeditions"][exp], card):
            raise ValueError(
                f"Cannot place {card_id} on {EXPEDITION_NAMES[exp]} expedition"
            )

        player["expeditions"][exp].append(card)
        state["phase"] = "draw"
        state["last_discarded_expedition"] = None

        card_label = "wager" if card["value"] == 0 else str(card["value"])
        log = [f"{player['name']} plays {card_label} on {EXPEDITION_NAMES[exp]}"]
        return ActionResult(new_state=state, log=log)

    def _apply_discard(self, state, idx, action):
        if state["phase"] != "play":
            raise ValueError("Not in play phase")

        player = state["players"][idx]
        card_id = action.get("card_id")
        card = self._remove_card_from_hand(player, card_id)
        exp = card["expedition"]

        state["discard_piles"][exp].append(card)
        state["phase"] = "draw"
        state["last_discarded_expedition"] = exp

        card_label = "wager" if card["value"] == 0 else str(card["value"])
        log = [f"{player['name']} discards {card_label} to {EXPEDITION_NAMES[exp]}"]
        return ActionResult(new_state=state, log=log)

    def _apply_draw(self, state, idx, action):
        if state["phase"] != "draw":
            raise ValueError("Not in draw phase")

        player = state["players"][idx]
        source = action.get("source")
        log = []

        if source == "draw_pile":
            if not state["draw_pile"]:
                raise ValueError("Draw pile is empty")
            card = state["draw_pile"].pop()
            player["hand"].append(card)
            log.append(f"{player['name']} draws from the draw pile")
        elif source == "discard":
            exp = action.get("expedition")
            if not exp or exp not in EXPEDITIONS:
                raise ValueError(f"Invalid expedition: {exp}")
            if exp == state.get("last_discarded_expedition"):
                raise ValueError("Cannot draw the card you just discarded")
            pile = state["discard_piles"][exp]
            if not pile:
                raise ValueError(f"No cards in {EXPEDITION_NAMES[exp]} discard")
            card = pile.pop()
            player["hand"].append(card)
            log.append(
                f"{player['name']} draws from {EXPEDITION_NAMES[exp]} discard"
            )
        else:
            raise ValueError(f"Invalid draw source: {source}")

        # Check game end: draw pile empty
        game_over = len(state["draw_pile"]) == 0
        if game_over:
            state["game_over"] = True
            scores = [score_player(p) for p in state["players"]]
            state["scoring"] = scores
            if scores[0]["total"] > scores[1]["total"]:
                state["winner"] = 0
            elif scores[1]["total"] > scores[0]["total"]:
                state["winner"] = 1
            else:
                state["winner"] = "draw"
            log.append("Draw pile is empty — game over!")
            for i, p in enumerate(state["players"]):
                log.append(f"{p['name']}: {scores[i]['total']} points")
            if state["winner"] == "draw":
                log.append("It's a draw!")
            else:
                log.append(
                    f"{state['players'][state['winner']]['name']} wins!"
                )
        else:
            # Next player's turn
            state["current_player"] = 1 - state["current_player"]
            state["phase"] = "play"
            state["last_discarded_expedition"] = None

        return ActionResult(new_state=state, log=log, game_over=game_over)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _remove_card_from_hand(player, card_id):
        for i, c in enumerate(player["hand"]):
            if c["id"] == card_id:
                return player["hand"].pop(i)
        raise ValueError(f"Card {card_id} not in hand")
