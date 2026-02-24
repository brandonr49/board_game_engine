"""
Tests for Battle Line game engine.

Covers: formation evaluation, flag claim proof, turn flow,
tactics cards, victory conditions, and edge cases.
"""

import pytest
from copy import deepcopy

from server.battleline.state import (
    create_initial_state, check_win_condition, generate_troop_deck,
    generate_tactics_deck, get_available_troops, NUM_FLAGS, TROOP_COLORS,
)
from server.battleline.formations import (
    best_formation, can_claim_flag,
    WEDGE, PHALANX, BATTALION, SKIRMISH, HOST,
)
from server.battleline.engine import BattleLineEngine


# ── Helpers ───────────────────────────────────────────────────────────

def troop(color, value):
    return {"type": "troop", "color": color, "value": value}


def tactic(card_id):
    """Create a tactics card by id."""
    from server.battleline.state import TACTICS_CARDS
    info = TACTICS_CARDS[card_id]
    card = dict(info)
    card["id"] = card_id
    return card


def make_state(auto_claim=False):
    """Create a fresh 2-player state with deterministic hands."""
    state = create_initial_state(["p1", "p2"], ["Alice", "Bob"])
    state["auto_claim"] = auto_claim
    # Give each player a known hand for testing
    state["players"][0]["hand"] = [
        troop("red", 1), troop("red", 2), troop("red", 3),
        troop("blue", 4), troop("blue", 5), troop("blue", 6),
        troop("green", 7),
    ]
    state["players"][1]["hand"] = [
        troop("yellow", 1), troop("yellow", 2), troop("yellow", 3),
        troop("orange", 4), troop("orange", 5), troop("orange", 6),
        troop("purple", 7),
    ]
    return state


def play_troop_action(card_index, flag_index):
    return {"kind": "play_troop", "card_index": card_index, "flag_index": flag_index}


def claim_flag_action(flag_index):
    return {"kind": "claim_flag", "flag_index": flag_index}


def done_claiming_action():
    return {"kind": "done_claiming"}


def draw_card_action(deck="troop"):
    return {"kind": "draw_card", "deck": deck}


def do_full_turn(engine, state, player_id, play_action, draw_deck="troop"):
    """Execute a full turn: play card, done claiming, draw card."""
    result = engine.apply_action(state, player_id, play_action)
    state = result.new_state
    result = engine.apply_action(state, player_id, done_claiming_action())
    state = result.new_state
    result = engine.apply_action(state, player_id, draw_card_action(draw_deck))
    return result


# ══════════════════════════════════════════════════════════════════════
# Formation Evaluation Tests
# ══════════════════════════════════════════════════════════════════════

class TestFormations:

    def test_wedge(self):
        cards = [troop("red", 7), troop("red", 8), troop("red", 9)]
        rank, total = best_formation(cards)
        assert rank == WEDGE
        assert total == 24

    def test_phalanx(self):
        cards = [troop("red", 5), troop("blue", 5), troop("green", 5)]
        rank, total = best_formation(cards)
        assert rank == PHALANX
        assert total == 15

    def test_battalion_order(self):
        cards = [troop("red", 2), troop("red", 7), troop("red", 9)]
        rank, total = best_formation(cards)
        assert rank == BATTALION
        assert total == 18

    def test_skirmish_line(self):
        cards = [troop("red", 3), troop("blue", 4), troop("green", 5)]
        rank, total = best_formation(cards)
        assert rank == SKIRMISH
        assert total == 12

    def test_host(self):
        cards = [troop("red", 1), troop("blue", 5), troop("green", 9)]
        rank, total = best_formation(cards)
        assert rank == HOST
        assert total == 15

    def test_empty(self):
        rank, total = best_formation([])
        assert rank == HOST
        assert total == 0

    def test_wedge_with_leader_wild(self):
        """Alexander as wild can complete a wedge."""
        cards = [troop("red", 8), troop("red", 9), tactic("alexander")]
        rank, total = best_formation(cards)
        assert rank == WEDGE
        assert total == 27  # 8+9+10

    def test_companion_cavalry_wild(self):
        """Companion Cavalry is always value 8."""
        cards = [troop("blue", 7), troop("blue", 9), tactic("companion_cavalry")]
        rank, total = best_formation(cards)
        assert rank == WEDGE
        assert total == 24  # 7+8+9

    def test_shield_bearers_wild(self):
        """Shield Bearers: value 1-3."""
        cards = [troop("red", 1), troop("red", 2), tactic("shield_bearers")]
        rank, total = best_formation(cards)
        assert rank == WEDGE
        assert total == 6  # 1+2+3

    def test_shield_bearers_cannot_be_high(self):
        """Shield Bearers max value is 3, can't make a wedge of 8-9-10."""
        cards = [troop("red", 9), troop("red", 10), tactic("shield_bearers")]
        rank, total = best_formation(cards)
        # Best possible: battalion order (same color, not consecutive)
        assert rank == BATTALION

    def test_fog_ignores_formation_rank(self):
        """With fog, formation rank is HOST; maximize sum."""
        cards = [troop("red", 8), troop("red", 9), troop("red", 10)]
        rank, total = best_formation(cards, has_fog=True)
        assert rank == HOST
        assert total == 27

    def test_two_wilds(self):
        """Two wildcards: alexander + companion cavalry."""
        cards = [troop("red", 9), tactic("alexander"), tactic("companion_cavalry")]
        rank, total = best_formation(cards)
        # Best: wedge with red 8, red 9, red 10 → sum 27
        assert rank == WEDGE
        assert total == 27


# ══════════════════════════════════════════════════════════════════════
# Flag Claim Proof Tests
# ══════════════════════════════════════════════════════════════════════

class TestClaimProof:

    def test_complete_vs_complete_winner(self):
        """Claimer wins with better formation."""
        state = make_state()
        # Flag 0: claimer has wedge (red 8,9,10), opponent has host
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["slots"][1] = [troop("yellow", 1), troop("blue", 3), troop("green", 7)]
        state["flags"][0]["completion_turn"] = [1, 2]

        assert can_claim_flag(state, 0, 0) is True

    def test_complete_vs_complete_loser(self):
        """Claimer loses with worse formation."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("yellow", 1), troop("blue", 3), troop("green", 7)]
        state["flags"][0]["slots"][1] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["completion_turn"] = [1, 2]

        assert can_claim_flag(state, 0, 0) is False

    def test_complete_vs_complete_tie_first_completer_wins(self):
        """Same formation — whoever completed first wins."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["slots"][1] = [troop("blue", 8), troop("blue", 9), troop("blue", 10)]
        state["flags"][0]["completion_turn"] = [1, 3]

        assert can_claim_flag(state, 0, 0) is True   # completed first
        assert can_claim_flag(state, 1, 0) is False   # completed later

    def test_incomplete_opponent_no_possible_beat(self):
        """Opponent has 2 cards and can't possibly beat claimer."""
        state = make_state()
        # Claimer: wedge 8-9-10
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["completion_turn"][0] = 1

        # Opponent: 2 low cards, no way to beat wedge 27
        state["flags"][0]["slots"][1] = [troop("yellow", 1), troop("blue", 2)]

        # Put the highest value cards on other flags so opponent can't get them
        # Place all color-10 cards visible
        for i, color in enumerate(["blue", "yellow", "green", "purple", "orange"]):
            if i + 1 < NUM_FLAGS:
                state["flags"][i + 1]["slots"][0].append(troop(color, 10))
                state["flags"][i + 1]["slots"][0].append(troop(color, 9))

        assert can_claim_flag(state, 0, 0) is True

    def test_incomplete_opponent_could_beat(self):
        """Opponent could still beat claimer — can't claim."""
        state = make_state()
        # Claimer: skirmish 1-2-3 (rank 2, sum 6) — weak formation
        state["flags"][0]["slots"][0] = [troop("red", 1), troop("blue", 2), troop("green", 3)]
        state["flags"][0]["completion_turn"][0] = 1

        # Opponent: 2 red cards, could make a wedge
        state["flags"][0]["slots"][1] = [troop("red", 9), troop("red", 10)]

        # red 8 is still available (not on any flag or discard)
        assert can_claim_flag(state, 0, 0) is False

    def test_claimer_incomplete_cannot_claim(self):
        """Claimer with fewer than required cards cannot claim."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9)]
        assert can_claim_flag(state, 0, 0) is False

    def test_already_claimed(self):
        """Can't claim an already-claimed flag."""
        state = make_state()
        state["flags"][0]["claimed_by"] = 1
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        assert can_claim_flag(state, 0, 0) is False


# ══════════════════════════════════════════════════════════════════════
# Turn Flow Tests
# ══════════════════════════════════════════════════════════════════════

class TestTurnFlow:

    def setup_method(self):
        self.engine = BattleLineEngine()

    def test_basic_turn_play_claim_draw(self):
        """Full turn: play troop → done claiming → draw card → next player."""
        state = make_state()
        assert state["current_player"] == 0
        assert state["phase"] == "play_card"

        # Play red 1 on flag 0
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state
        assert state["phase"] == "claim_flags"

        # Done claiming
        result = self.engine.apply_action(state, "p1", done_claiming_action())
        state = result.new_state
        assert state["phase"] == "draw_card"

        # Draw from troop deck
        result = self.engine.apply_action(state, "p1", draw_card_action("troop"))
        state = result.new_state
        assert state["current_player"] == 1
        assert state["phase"] == "play_card"

    def test_wrong_player_rejected(self):
        state = make_state()
        with pytest.raises(ValueError, match="Not your turn"):
            self.engine.apply_action(state, "p2", play_troop_action(0, 0))

    def test_card_placed_on_flag(self):
        state = make_state()
        card = state["players"][0]["hand"][0]  # red 1
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state
        assert state["flags"][0]["slots"][0] == [card]
        assert len(state["players"][0]["hand"]) == 6

    def test_alternating_turns(self):
        """Players alternate: p1 → p2 → p1."""
        state = make_state()
        result = do_full_turn(self.engine, state, "p1", play_troop_action(0, 0))
        state = result.new_state
        assert state["current_player"] == 1

        result = do_full_turn(self.engine, state, "p2", play_troop_action(0, 1))
        state = result.new_state
        assert state["current_player"] == 0

    def test_draw_from_tactics_deck(self):
        state = make_state()
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state
        result = self.engine.apply_action(state, "p1", done_claiming_action())
        state = result.new_state

        initial_tactics = len(state["tactics_deck"])
        result = self.engine.apply_action(state, "p1", draw_card_action("tactics"))
        state = result.new_state
        assert len(state["tactics_deck"]) == initial_tactics - 1

    def test_player_view_hides_opponent_hand(self):
        state = make_state()
        view = self.engine.get_player_view(state, "p1")
        # Own hand: list of cards
        assert isinstance(view["players"][0]["hand"], list)
        # Opponent hand: count only
        assert isinstance(view["players"][1]["hand"], int)
        assert view["players"][1]["hand"] == 7

    def test_player_view_hides_decks(self):
        state = make_state()
        view = self.engine.get_player_view(state, "p1")
        assert isinstance(view["troop_deck"], int)
        assert isinstance(view["tactics_deck"], int)


# ══════════════════════════════════════════════════════════════════════
# Tactics Card Tests
# ══════════════════════════════════════════════════════════════════════

class TestTactics:

    def setup_method(self):
        self.engine = BattleLineEngine()

    def test_tactics_limit(self):
        """Can't play more tactics than opponent has played."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("fog"), tactic("mud")]
        state["players"][0]["tactics_played"] = 1
        state["players"][1]["tactics_played"] = 0

        # Already played 1 tactic, opponent played 0 — can't play another
        with pytest.raises(ValueError, match="Cannot play more tactics"):
            self.engine.apply_action(state, "p1", {"kind": "play_environment", "card_index": 0, "flag_index": 0})

    def test_tactics_limit_allows_equal(self):
        """Can play if equal to opponent's count."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("fog")] + [troop("red", i) for i in range(1, 7)]
        state["players"][0]["tactics_played"] = 0
        state["players"][1]["tactics_played"] = 0

        result = self.engine.apply_action(state, "p1", {"kind": "play_environment", "card_index": 0, "flag_index": 0})
        assert "Fog" in result.log[0]

    def test_leader_limit(self):
        """Can't play second leader when one is already on board."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("darius")] + [troop("red", i) for i in range(1, 7)]
        state["players"][0]["has_leader_on_board"] = True
        state["players"][0]["tactics_played"] = 0
        state["players"][1]["tactics_played"] = 1  # allow tactic play

        with pytest.raises(ValueError, match="already have a leader"):
            self.engine.apply_action(state, "p1", {"kind": "play_morale_tactic", "card_index": 0, "flag_index": 0})

    def test_play_alexander(self):
        """Play Alexander as morale tactic onto a flag."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("alexander")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_morale_tactic", "card_index": 0, "flag_index": 0})
        state = result.new_state
        assert state["players"][0]["has_leader_on_board"] is True
        assert state["players"][0]["tactics_played"] == 1
        assert state["flags"][0]["slots"][0][0]["id"] == "alexander"

    def test_fog_on_flag(self):
        """Fog placed in environment list, not in player slots."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("fog")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_environment", "card_index": 0, "flag_index": 2})
        state = result.new_state
        assert "fog" in state["flags"][2]["environment"]
        assert len(state["flags"][2]["slots"][0]) == 0  # not in slots

    def test_mud_changes_required_cards(self):
        """Mud increases required cards to 4."""
        state = make_state()
        state["flags"][0]["environment"] = ["mud"]
        state["flags"][0]["slots"][0] = [troop("red", 1), troop("red", 2), troop("red", 3)]
        state["flags"][0]["completion_turn"] = [None, None]

        # 3 cards not enough with mud — can't claim
        assert can_claim_flag(state, 0, 0) is False

    def test_scout_multi_step(self):
        """Scout: draw 3, return 2."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("scout")] + [troop("red", i) for i in range(1, 7)]

        # Play scout
        result = self.engine.apply_action(state, "p1", {"kind": "play_scout", "card_index": 0})
        state = result.new_state
        assert state["sub_phase"] == "scout_draw"
        assert state["scout_state"]["draws_remaining"] == 3

        # Draw 3 cards
        for i in range(3):
            result = self.engine.apply_action(state, "p1", {"kind": "scout_draw_card", "deck": "troop"})
            state = result.new_state

        assert state["sub_phase"] == "scout_return"
        assert len(state["players"][0]["hand"]) == 9  # 6 + 3

        # Return 2 cards
        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state

        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state

        # Should be back to claim_flags phase
        assert state["phase"] == "claim_flags"
        assert state["scout_state"] is None
        assert len(state["players"][0]["hand"]) == 7  # net +1

    def test_redeploy(self):
        """Redeploy: pick own card, place on different flag."""
        state = make_state()
        # Put a card on flag 0
        state["flags"][0]["slots"][0] = [troop("red", 5)]

        state["players"][0]["hand"] = [tactic("redeploy")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_redeploy", "card_index": 0})
        state = result.new_state
        assert state["sub_phase"] == "redeploy_pick"

        # Pick the card from flag 0
        result = self.engine.apply_action(state, "p1", {"kind": "redeploy_pick", "flag_index": 0, "card_index_at_flag": 0})
        state = result.new_state
        assert state["sub_phase"] == "redeploy_place"
        assert len(state["flags"][0]["slots"][0]) == 0

        # Place on flag 3
        result = self.engine.apply_action(state, "p1", {"kind": "redeploy_place_to_flag", "flag_index": 3})
        state = result.new_state
        assert state["phase"] == "claim_flags"
        assert len(state["flags"][3]["slots"][0]) == 1
        assert state["flags"][3]["slots"][0][0] == troop("red", 5)

    def test_redeploy_discard(self):
        """Redeploy: pick own card, discard it."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 5)]
        state["players"][0]["hand"] = [tactic("redeploy")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_redeploy", "card_index": 0})
        state = result.new_state

        result = self.engine.apply_action(state, "p1", {"kind": "redeploy_pick", "flag_index": 0, "card_index_at_flag": 0})
        state = result.new_state

        result = self.engine.apply_action(state, "p1", {"kind": "redeploy_discard"})
        state = result.new_state
        assert state["phase"] == "claim_flags"
        assert len(state["discard"][0]) == 2  # redeploy card + discarded troop

    def test_deserter(self):
        """Deserter: remove an opponent card."""
        state = make_state()
        state["flags"][2]["slots"][1] = [troop("yellow", 10)]
        state["players"][0]["hand"] = [tactic("deserter")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_deserter", "card_index": 0})
        state = result.new_state
        assert state["sub_phase"] == "deserter_pick"

        result = self.engine.apply_action(state, "p1", {"kind": "deserter_pick", "flag_index": 2, "card_index_at_flag": 0})
        state = result.new_state
        assert state["phase"] == "claim_flags"
        assert len(state["flags"][2]["slots"][1]) == 0
        # Card goes to opponent's discard
        assert state["discard"][1][0] == troop("yellow", 10)

    def test_traitor(self):
        """Traitor: steal opponent troop, place on own flag."""
        state = make_state()
        state["flags"][2]["slots"][1] = [troop("yellow", 10)]
        state["players"][0]["hand"] = [tactic("traitor")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_traitor", "card_index": 0})
        state = result.new_state
        assert state["sub_phase"] == "traitor_pick"

        result = self.engine.apply_action(state, "p1", {"kind": "traitor_pick", "flag_index": 2, "card_index_at_flag": 0})
        state = result.new_state
        assert state["sub_phase"] == "traitor_place"

        result = self.engine.apply_action(state, "p1", {"kind": "traitor_place", "flag_index": 5})
        state = result.new_state
        assert state["phase"] == "claim_flags"
        assert state["flags"][5]["slots"][0][0] == troop("yellow", 10)
        assert len(state["flags"][2]["slots"][1]) == 0

    def test_traitor_cannot_steal_tactics(self):
        """Traitor can only steal troop cards, not tactics."""
        state = make_state()
        # Opponent has only a tactics card on unclaimed flags — no troops
        state["flags"][2]["slots"][1] = [tactic("alexander")]
        state["players"][0]["hand"] = [tactic("traitor")] + [troop("red", i) for i in range(1, 7)]
        state["players"][1]["tactics_played"] = 1  # allow tactic play

        # Can't even play Traitor: no opponent troops to target
        with pytest.raises(ValueError, match="No opponent troops"):
            self.engine.apply_action(state, "p1", {"kind": "play_traitor", "card_index": 0})

    def test_traitor_pick_rejects_tactics_card(self):
        """During traitor_pick phase, selecting a non-troop card is rejected."""
        state = make_state()
        # Opponent has a troop AND a tactics card
        state["flags"][2]["slots"][1] = [troop("yellow", 5), tactic("alexander")]
        state["players"][0]["hand"] = [tactic("traitor")] + [troop("red", i) for i in range(1, 7)]
        state["players"][1]["tactics_played"] = 1

        result = self.engine.apply_action(state, "p1", {"kind": "play_traitor", "card_index": 0})
        state = result.new_state

        # Picking the tactics card (index 1) should fail
        with pytest.raises(ValueError, match="only steal troop"):
            self.engine.apply_action(state, "p1", {"kind": "traitor_pick", "flag_index": 2, "card_index_at_flag": 1})


# ══════════════════════════════════════════════════════════════════════
# Victory Condition Tests
# ══════════════════════════════════════════════════════════════════════

class TestVictory:

    def test_breakthrough_3_adjacent(self):
        """3 adjacent claimed flags wins."""
        state = make_state()
        state["flags"][3]["claimed_by"] = 0
        state["flags"][4]["claimed_by"] = 0
        state["flags"][5]["claimed_by"] = 0

        assert check_win_condition(state) == 0

    def test_envelopment_5_flags(self):
        """5 total claimed flags wins."""
        state = make_state()
        for i in [0, 2, 4, 6, 8]:
            state["flags"][i]["claimed_by"] = 1
        assert check_win_condition(state) == 1

    def test_no_win(self):
        """No win with 2 adjacent and 4 total."""
        state = make_state()
        state["flags"][0]["claimed_by"] = 0
        state["flags"][1]["claimed_by"] = 0
        state["flags"][3]["claimed_by"] = 0
        state["flags"][5]["claimed_by"] = 0
        assert check_win_condition(state) is None

    def test_breakthrough_at_edges(self):
        """Breakthrough works at start and end of flag line."""
        state = make_state()
        state["flags"][0]["claimed_by"] = 0
        state["flags"][1]["claimed_by"] = 0
        state["flags"][2]["claimed_by"] = 0
        assert check_win_condition(state) == 0

        state2 = make_state()
        state2["flags"][6]["claimed_by"] = 1
        state2["flags"][7]["claimed_by"] = 1
        state2["flags"][8]["claimed_by"] = 1
        assert check_win_condition(state2) == 1

    def test_win_ends_game(self):
        """Claiming a winning flag triggers game_over in engine."""
        engine = BattleLineEngine()
        state = make_state()

        # Set up 2 adjacent claimed + a third ready to claim
        state["flags"][3]["claimed_by"] = 0
        state["flags"][4]["claimed_by"] = 0
        # Flag 5: player 0 has a wedge, player 1 has nothing
        state["flags"][5]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][5]["completion_turn"][0] = 1

        # Play a card first to get to claim_flags phase
        result = engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state

        # Claim flag 5
        result = engine.apply_action(state, "p1", claim_flag_action(5))
        assert result.game_over is True
        assert result.new_state["winner"] == 0


# ══════════════════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def setup_method(self):
        self.engine = BattleLineEngine()

    def test_empty_decks_auto_skip_draw(self):
        """When both decks empty, draw phase is skipped."""
        state = make_state()
        state["troop_deck"] = []
        state["tactics_deck"] = []

        # Play a card
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state

        # Done claiming — should auto-advance to next player
        result = self.engine.apply_action(state, "p1", done_claiming_action())
        state = result.new_state
        assert state["current_player"] == 1
        assert state["phase"] == "play_card"

    def test_pass_when_no_troops(self):
        """Can pass when hand has no troop cards."""
        state = make_state()
        state["players"][0]["hand"] = [tactic("fog"), tactic("mud")]
        # Make both unplayable (tactics limit)
        state["players"][0]["tactics_played"] = 1
        state["players"][1]["tactics_played"] = 0

        result = self.engine.apply_action(state, "p1", {"kind": "pass"})
        state = result.new_state
        assert state["phase"] == "claim_flags"

    def test_pass_when_all_flags_full(self):
        """Can pass when all unclaimed flags have full slots."""
        state = make_state()
        # Fill all flags for player 0
        for fi in range(NUM_FLAGS):
            state["flags"][fi]["slots"][0] = [troop("red", 1), troop("red", 2), troop("red", 3)]

        result = self.engine.apply_action(state, "p1", {"kind": "pass"})
        state = result.new_state
        assert state["phase"] == "claim_flags"

    def test_cannot_pass_with_troops_and_open_flags(self):
        """Cannot pass when you have troop cards and open flag slots."""
        state = make_state()
        with pytest.raises(ValueError, match="must play a card"):
            self.engine.apply_action(state, "p1", {"kind": "pass"})

    def test_cannot_play_on_claimed_flag(self):
        """Cannot place a card on a claimed flag."""
        state = make_state()
        state["flags"][0]["claimed_by"] = 1

        with pytest.raises(ValueError, match="Flag already claimed"):
            self.engine.apply_action(state, "p1", play_troop_action(0, 0))

    def test_cannot_play_on_full_flag(self):
        """Cannot place a card when flag side is full."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 1), troop("red", 2), troop("red", 3)]

        with pytest.raises(ValueError, match="Flag side is full"):
            self.engine.apply_action(state, "p1", play_troop_action(0, 0))

    def test_game_over_prevents_actions(self):
        """No actions possible after game is over."""
        state = make_state()
        state["winner"] = 0

        with pytest.raises(ValueError, match="Game is over"):
            self.engine.apply_action(state, "p1", play_troop_action(0, 0))

    def test_get_waiting_for_returns_current_player(self):
        state = make_state()
        assert self.engine.get_waiting_for(state) == ["p1"]

        state["current_player"] = 1
        assert self.engine.get_waiting_for(state) == ["p2"]

    def test_get_waiting_for_empty_when_game_over(self):
        state = make_state()
        state["winner"] = 0
        assert self.engine.get_waiting_for(state) == []

    def test_initial_state_requires_2_players(self):
        engine = BattleLineEngine()
        with pytest.raises(ValueError, match="exactly 2"):
            engine.initial_state(["p1", "p2", "p3"], ["A", "B", "C"])

    def test_available_troops_excludes_visible(self):
        """get_available_troops excludes cards on flags and in discard."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 10)]
        state["discard"][0] = [troop("blue", 10)]

        available = get_available_troops(state)
        assert ("red", 10) not in available
        assert ("blue", 10) not in available
        assert ("green", 10) in available  # not visible
        assert len(available) == 58  # 60 - 2

    def test_completion_turn_tracking(self):
        """Completion turn is set when side reaches required count."""
        state = make_state()
        state["turn_number"] = 5

        engine = BattleLineEngine()

        # Play 3 cards on flag 0
        state["players"][0]["hand"] = [troop("red", i) for i in range(1, 8)]
        for i in range(3):
            result = engine.apply_action(state, "p1", play_troop_action(0, 0))
            state = result.new_state
            # done claiming + draw to complete turn
            result = engine.apply_action(state, "p1", done_claiming_action())
            state = result.new_state
            if state["phase"] == "draw_card":
                result = engine.apply_action(state, "p1", draw_card_action())
                state = result.new_state

            # Let p2 play too
            if state["current_player"] == 1:
                state["players"][1]["hand"] = [troop("yellow", j) for j in range(1, 8)]
                result = engine.apply_action(state, "p2", play_troop_action(0, 1))
                state = result.new_state
                result = engine.apply_action(state, "p2", done_claiming_action())
                state = result.new_state
                if state["phase"] == "draw_card":
                    result = engine.apply_action(state, "p2", draw_card_action())
                    state = result.new_state

        # Flag 0 should have completion_turn set for player 0
        assert state["flags"][0]["completion_turn"][0] is not None

    def test_redeploy_cannot_place_same_flag(self):
        """Redeploy can't place card back on the same flag."""
        state = make_state()
        state["flags"][0]["slots"][0] = [troop("red", 5), troop("red", 6)]
        state["players"][0]["hand"] = [tactic("redeploy")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_redeploy", "card_index": 0})
        state = result.new_state

        result = self.engine.apply_action(state, "p1", {"kind": "redeploy_pick", "flag_index": 0, "card_index_at_flag": 0})
        state = result.new_state

        with pytest.raises(ValueError, match="Cannot redeploy to the same flag"):
            self.engine.apply_action(state, "p1", {"kind": "redeploy_place_to_flag", "flag_index": 0})


# ══════════════════════════════════════════════════════════════════════
# State Generation Tests
# ══════════════════════════════════════════════════════════════════════

class TestStateGeneration:

    def test_troop_deck_has_60_cards(self):
        deck = generate_troop_deck()
        assert len(deck) == 60
        # All unique
        cards = [(c["color"], c["value"]) for c in deck]
        assert len(set(cards)) == 60

    def test_tactics_deck_has_10_cards(self):
        deck = generate_tactics_deck()
        assert len(deck) == 10
        ids = [c["id"] for c in deck]
        assert len(set(ids)) == 10

    def test_initial_state_structure(self):
        state = create_initial_state(["p1", "p2"], ["Alice", "Bob"])
        assert state["game"] == "battleline"
        assert len(state["players"]) == 2
        assert len(state["flags"]) == 9
        assert state["current_player"] == 0
        assert state["phase"] == "play_card"
        assert state["winner"] is None

        # Each player dealt 7 cards
        for p in state["players"]:
            assert len(p["hand"]) == 7

        # 60 - 14 = 46 remaining in troop deck
        assert len(state["troop_deck"]) == 46
        assert len(state["tactics_deck"]) == 10


# ══════════════════════════════════════════════════════════════════════
# Integration: Phase Info
# ══════════════════════════════════════════════════════════════════════

class TestPhaseInfo:

    def test_phase_info_play_card(self):
        engine = BattleLineEngine()
        state = make_state()
        info = engine.get_phase_info(state)
        assert info["phase"] == "play_card"
        assert "Alice" in info["description"]

    def test_phase_info_after_play(self):
        engine = BattleLineEngine()
        state = make_state()
        result = engine.apply_action(state, "p1", play_troop_action(0, 0))
        info = engine.get_phase_info(result.new_state)
        assert info["phase"] == "claim_flags"


# ══════════════════════════════════════════════════════════════════════
# Auto-Claim Tests
# ══════════════════════════════════════════════════════════════════════

class TestAutoClaim:

    def setup_method(self):
        self.engine = BattleLineEngine()

    def test_auto_claim_skips_claim_phase(self):
        """With auto_claim on, playing a card skips claim_flags → draw_card."""
        state = make_state(auto_claim=True)
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        assert result.new_state["phase"] == "draw_card"

    def test_auto_claim_claims_provable_flags(self):
        """Auto-claim claims flags that are provably won."""
        state = make_state(auto_claim=True)
        # Flag 0: player 0 has a wedge, player 1 has nothing
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["completion_turn"][0] = 1

        # Play a card on a different flag to trigger claim phase
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 1))
        s = result.new_state
        assert s["flags"][0]["claimed_by"] == 0
        assert s["phase"] == "draw_card"
        assert any("claims flag 1" in msg for msg in result.log)

    def test_auto_claim_off_enters_manual_claim(self):
        """With auto_claim off, playing enters claim_flags phase."""
        state = make_state(auto_claim=False)
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        assert result.new_state["phase"] == "claim_flags"

    def test_toggle_auto_claim(self):
        """Toggle action flips auto_claim state."""
        state = make_state(auto_claim=True)
        result = self.engine.apply_action(state, "p1", {"kind": "toggle_auto_claim"})
        assert result.new_state["auto_claim"] is False
        assert "Auto-claim turned off" in result.log

        result2 = self.engine.apply_action(result.new_state, "p1", {"kind": "toggle_auto_claim"})
        assert result2.new_state["auto_claim"] is True
        assert "Auto-claim turned on" in result2.log

    def test_toggle_in_valid_actions(self):
        """toggle_auto_claim appears in valid actions."""
        state = make_state()
        actions = self.engine.get_valid_actions(state, "p1")
        kinds = [a["kind"] for a in actions]
        assert "toggle_auto_claim" in kinds

    def test_auto_claim_triggers_win(self):
        """Auto-claiming a winning flag ends the game."""
        state = make_state(auto_claim=True)
        # 2 adjacent flags already claimed
        state["flags"][3]["claimed_by"] = 0
        state["flags"][4]["claimed_by"] = 0
        # Flag 5: player 0 has a wedge
        state["flags"][5]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][5]["completion_turn"][0] = 1

        # Play a card — auto-claim should claim flag 5 and trigger win
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        assert result.game_over is True
        assert result.new_state["winner"] == 0

    def test_auto_claim_empty_decks_advances_turn(self):
        """With empty decks, auto-claim skips draw phase too."""
        state = make_state(auto_claim=True)
        state["troop_deck"] = []
        state["tactics_deck"] = []

        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        s = result.new_state
        assert s["current_player"] == 1
        assert s["phase"] == "play_card"

    def test_full_turn_with_auto_claim(self):
        """Full turn with auto-claim: play → draw (claim skipped)."""
        state = make_state(auto_claim=True)
        result = self.engine.apply_action(state, "p1", play_troop_action(0, 0))
        state = result.new_state
        assert state["phase"] == "draw_card"

        result = self.engine.apply_action(state, "p1", draw_card_action("troop"))
        state = result.new_state
        assert state["current_player"] == 1
        assert state["phase"] == "play_card"


# ── Bug Fix Regression Tests ────────────────────────────────────────

class TestScoutSkipsDraw:
    """Scout's draw-3-return-2 replaces the normal end-of-turn draw."""

    engine = BattleLineEngine()

    def test_scout_skips_draw_auto_claim_on(self):
        """After Scout, turn advances directly (no draw phase) with auto-claim."""
        state = make_state(auto_claim=True)
        state["players"][0]["hand"] = [tactic("scout")] + [troop("red", i) for i in range(1, 7)]
        initial_hand_size = len(state["players"][0]["hand"])  # 7

        # Play scout
        result = self.engine.apply_action(state, "p1", {"kind": "play_scout", "card_index": 0})
        state = result.new_state
        assert state["sub_phase"] == "scout_draw"

        # Draw 3
        for _ in range(3):
            result = self.engine.apply_action(state, "p1", {"kind": "scout_draw_card", "deck": "troop"})
            state = result.new_state

        # Return 2
        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state
        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state

        # Should advance to opponent's turn (no draw phase)
        assert state["current_player"] == 1
        assert state["phase"] == "play_card"
        # Scout card removed from hand (-1), drew 3, returned 2 = net +0 from initial 7
        # Initial: 7 cards (scout + 6 troops)
        # After: -1 scout, +3 drawn, -2 returned = 7 cards
        assert len(state["players"][0]["hand"]) == 7

    def test_scout_skips_draw_auto_claim_off(self):
        """After Scout with manual claiming, done_claiming skips draw."""
        state = make_state(auto_claim=False)
        state["players"][0]["hand"] = [tactic("scout")] + [troop("red", i) for i in range(1, 7)]

        # Play scout
        result = self.engine.apply_action(state, "p1", {"kind": "play_scout", "card_index": 0})
        state = result.new_state

        # Draw 3
        for _ in range(3):
            result = self.engine.apply_action(state, "p1", {"kind": "scout_draw_card", "deck": "troop"})
            state = result.new_state

        # Return 2
        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state
        result = self.engine.apply_action(state, "p1", {"kind": "scout_return_card", "card_index": 0, "deck": "troop"})
        state = result.new_state

        # Should be in claim_flags (manual mode)
        assert state["phase"] == "claim_flags"

        # Done claiming — should skip draw and advance turn
        result = self.engine.apply_action(state, "p1", {"kind": "done_claiming"})
        state = result.new_state
        assert state["current_player"] == 1
        assert state["phase"] == "play_card"
        assert len(state["players"][0]["hand"]) == 7  # net +0


class TestMudClearsCompletion:
    """Mud should clear completion_turn when a 3-card side becomes incomplete."""

    engine = BattleLineEngine()

    def test_mud_clears_completion_turn(self):
        """Playing Mud clears completion_turn for sides with exactly 3 cards."""
        state = make_state()
        # Fill flag 0 with 3 cards for player 0
        state["flags"][0]["slots"][0] = [troop("red", 8), troop("red", 9), troop("red", 10)]
        state["flags"][0]["completion_turn"][0] = 5  # was completed on turn 5

        # Give player 0 the mud card
        state["players"][0]["hand"] = [tactic("mud")] + [troop("red", i) for i in range(1, 7)]

        # Play mud on flag 0
        result = self.engine.apply_action(state, "p1", {"kind": "play_environment", "card_index": 0, "flag_index": 0})
        state = result.new_state

        # Completion should be cleared (3 cards < 4 required with mud)
        assert state["flags"][0]["completion_turn"][0] is None
        assert "mud" in state["flags"][0]["environment"]

    def test_mud_preserves_completion_if_four_cards(self):
        """If a side already has 4 cards when Mud is played, completion is preserved."""
        state = make_state()
        # Put 4 cards on flag 0 for player 0 (unusual, but possible via other tactics)
        state["flags"][0]["slots"][0] = [
            troop("red", 7), troop("red", 8), troop("red", 9), troop("red", 10)
        ]
        state["flags"][0]["completion_turn"][0] = 5

        state["players"][0]["hand"] = [tactic("mud")] + [troop("red", i) for i in range(1, 7)]

        result = self.engine.apply_action(state, "p1", {"kind": "play_environment", "card_index": 0, "flag_index": 0})
        state = result.new_state

        # 4 cards >= 4 required — completion_turn should NOT be cleared
        # (uncheck only clears when count < required)
        assert state["flags"][0]["completion_turn"][0] == 5


class TestConsecutivePassDraw:
    """Two consecutive passes should end the game as a draw."""

    engine = BattleLineEngine()

    def test_two_consecutive_passes_draw(self):
        """Both players passing in succession ends the game."""
        state = make_state()
        # Empty both players' hands of troops so they can pass
        state["players"][0]["hand"] = []
        state["players"][1]["hand"] = []
        # Empty decks so draw phase is skipped
        state["troop_deck"] = []
        state["tactics_deck"] = []

        # Player 0 passes
        result = self.engine.apply_action(state, "p1", {"kind": "pass"})
        state = result.new_state
        assert state["winner"] is None or state["winner"] == "draw"

        if state["winner"] is None:
            # Advance through claim phase
            result = self.engine.apply_action(state, "p1", {"kind": "done_claiming"})
            state = result.new_state

        # If not already draw, player 1 passes
        if state["winner"] is None:
            result = self.engine.apply_action(state, "p2", {"kind": "pass"})
            state = result.new_state

        assert state["winner"] == "draw"
        assert result.game_over is True

    def test_pass_then_play_resets_counter(self):
        """A non-pass action resets the consecutive pass counter."""
        state = make_state()
        state["players"][0]["hand"] = []
        state["troop_deck"] = []
        state["tactics_deck"] = []

        # Player 0 passes
        result = self.engine.apply_action(state, "p1", {"kind": "pass"})
        state = result.new_state
        assert state["consecutive_passes"] == 1

        # Advance through claims
        result = self.engine.apply_action(state, "p1", {"kind": "done_claiming"})
        state = result.new_state

        # Player 1 plays a troop instead of passing
        state["players"][1]["hand"] = [troop("red", 1)]
        result = self.engine.apply_action(state, "p2", {"kind": "play_troop", "card_index": 0, "flag_index": 0})
        state = result.new_state
        assert state["consecutive_passes"] == 0
