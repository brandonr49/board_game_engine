"""TAMSK game engine — GameEngine subclass implementing all 3 levels."""

import time
from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.tamsk.state import (
    RINGS_PER_PLAYER, HOURGLASS_TIMER_SECS, PRESSURE_TIMER_SECS,
    hex_key, parse_hex, hex_neighbors, generate_board, create_player,
    setup_hourglasses, get_player_hourglasses, get_hourglass_at,
)


class TamskEngine(GameEngine):
    player_count_range = (2, 2)

    # ── Abstract method implementations ──────────────────

    def initial_state(self, player_ids, player_names):
        players = [
            create_player(i, pid, name)
            for i, (pid, name) in enumerate(zip(player_ids, player_names))
        ]
        return {
            "game": "tamsk",
            "player_ids": list(player_ids),
            "player_count": 2,
            "players": players,
            "board": generate_board(),
            "hourglasses": {},  # populated after config
            "current_player": 0,
            "phase": "config",
            "sub_phase": None,
            "level": 1,
            "turn_number": 0,
            "turns_taken": [0, 0],
            "hourglasses_moved_initial": [[], []],
            "consecutive_passes": 0,
            "moved_to_space": None,
            "ring_window_start": None,
            "ring_window_space": None,
            "ring_window_mover": None,
            "pressure_timer": {
                "timer_remaining": PRESSURE_TIMER_SECS,
                "timer_started_at": None,  # null = sand not flowing
                "active": False,           # flipped more recently than last move
                "activated_by": None,      # player_id who last flipped it
            },
            "bonus_rings": [0, 0],
            "game_over": False,
            "winner": None,
        }

    def get_player_view(self, state, player_id):
        view = deepcopy(state)
        self._check_timers(view)
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
            return self._valid_play_actions(state, player_id, player_idx)
        return []

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        game_ended = self._check_timers(state)

        kind = action.get("kind")
        player_idx = self._player_index(state, player_id)
        if player_idx is None:
            raise ValueError("Unknown player")

        if game_ended:
            return ActionResult(state, log=["Game ended — timers expired."], game_over=True)

        if state["game_over"]:
            raise ValueError("Game is over")

        # Auto-expire ring window if > 6 seconds
        if state.get("sub_phase") == "ring_window" and state.get("ring_window_start"):
            elapsed = time.time() - state["ring_window_start"]
            if elapsed >= 6.0 and kind != "place_ring":
                state["ring_window_start"] = None
                state["ring_window_space"] = None
                state["ring_window_mover"] = None
                cp = state["current_player"]
                return self._maybe_enter_bonus_ring_phase(state, cp, ["Ring window expired."])

        if kind == "set_level":
            return self._apply_set_level(state, player_idx, action)
        elif kind == "move_hourglass":
            return self._apply_move_hourglass(state, player_id, player_idx, action)
        elif kind == "place_ring":
            return self._apply_place_ring(state, player_id, player_idx, action)
        elif kind == "pass":
            return self._apply_pass(state, player_id, player_idx)
        elif kind == "place_bonus_ring":
            return self._apply_place_bonus_ring(state, player_id, player_idx, action)
        elif kind == "skip_bonus_ring":
            return self._apply_skip_bonus_ring(state, player_id, player_idx)
        elif kind == "activate_pressure":
            return self._apply_activate_pressure(state, player_id, player_idx)
        else:
            raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []
        if state["phase"] == "config":
            return [state["player_ids"][0]]  # host only
        # ring_window: both players can act (mover first 3s, then either)
        if state.get("sub_phase") == "ring_window":
            return list(state["player_ids"])
        # In play phase, the current player must act.
        # Level 3: the non-current player CAN act (pressure) but isn't required to.
        return [state["player_ids"][state["current_player"]]]

    def get_phase_info(self, state):
        phase = state["phase"]
        level = state["level"]
        cp = state["current_player"]
        player_name = state["players"][cp]["name"] if state["players"] else ""

        if phase == "config":
            desc = "Waiting for host to select difficulty level"
        elif phase == "play":
            sub = state.get("sub_phase", "move")
            if sub == "move":
                desc = f"{player_name}'s turn — move an hourglass"
            elif sub == "ring_window":
                desc = f"Ring placement window"
            elif sub == "bonus_ring":
                desc = f"{player_name}'s turn — place a bonus ring (pressure penalty)"
            else:
                desc = f"{player_name}'s turn"
        else:
            desc = "Game over"

        return {
            "phase": phase,
            "sub_phase": state.get("sub_phase"),
            "turn": state["turn_number"],
            "level": level,
            "description": desc,
            "current_player_name": player_name,
        }

    # ── Config phase ─────────────────────────────────────

    def _valid_config_actions(self, state, player_idx):
        if player_idx != 0:
            return []
        return [
            {"kind": "set_level", "level": 1},
            {"kind": "set_level", "level": 2},
            {"kind": "set_level", "level": 3},
        ]

    def _apply_set_level(self, state, player_idx, action):
        if state["phase"] != "config":
            raise ValueError("Not in config phase")
        if player_idx != 0:
            raise ValueError("Only the host can set the level")

        level = action.get("level")
        if level not in (1, 2, 3):
            raise ValueError("Level must be 1, 2, or 3")

        state["level"] = level
        state["hourglasses"] = setup_hourglasses()

        # Timers don't start until each hourglass is first moved (flipped)

        state["phase"] = "play"
        state["sub_phase"] = "move"
        state["current_player"] = 0

        level_names = {1: "No Timers", 2: "Timers Active", 3: "Full Game"}
        log = [f"Game started at Level {level} ({level_names[level]})."]
        return ActionResult(state, log=log)

    # ── Play phase: valid actions ────────────────────────

    def _valid_play_actions(self, state, player_id, player_idx):
        if state["phase"] != "play":
            return []

        sub = state.get("sub_phase", "move")
        cp = state["current_player"]
        actions = []

        if sub == "move" and player_idx == cp:
            actions = self._valid_move_actions(state, player_idx)
            # No pass action needed — auto-pass happens in _advance_turn

        elif sub == "ring_window":
            now = time.time()
            elapsed = now - (state.get("ring_window_start") or now)
            space_key = state.get("ring_window_space")
            if space_key:
                space = state["board"][space_key]
                can_place = len(space["rings"]) < space["capacity"]
                mover_idx = state.get("ring_window_mover")
                if can_place and state["players"][player_idx]["rings_remaining"] > 0:
                    if player_idx == mover_idx and elapsed < 3.0:
                        actions.append({"kind": "place_ring"})
                    elif elapsed >= 3.0:
                        actions.append({"kind": "place_ring"})

        elif sub == "bonus_ring" and player_idx == cp:
            # Pressure penalty: player chooses any board space for bonus ring
            player = state["players"][player_idx]
            if player["rings_remaining"] > 0:
                for space_key in state["board"]:
                    actions.append({
                        "kind": "place_bonus_ring",
                        "space": space_key,
                    })
            actions.append({"kind": "skip_bonus_ring"})

        # Level 3: non-current player can flip pressure timer (only at zero)
        if (state["level"] == 3
                and sub in ("move", "ring_window")
                and player_idx != cp):
            pt = state["pressure_timer"]
            now = time.time()
            remaining = pt["timer_remaining"]
            if pt["timer_started_at"] is not None:
                remaining = max(0, remaining - (now - pt["timer_started_at"]))
            if remaining <= 0:
                actions.append({"kind": "activate_pressure"})

        return actions

    def _valid_move_actions(self, state, player_idx):
        """Enumerate all valid hourglass moves for the current player."""
        player_color = state["players"][player_idx]["color"]
        hourglasses = get_player_hourglasses(state["hourglasses"], player_color)
        actions = []

        # Level 2/3: first 3 turns must each move a different hourglass
        forced_set = None
        if state["level"] >= 2:
            moved = state["hourglasses_moved_initial"][player_idx]
            if len(moved) < 3:
                all_ids = {h["id"] for h in hourglasses if not h["is_dead"]}
                forced_set = all_ids - set(moved)

        occupied = {h["position"] for h in state["hourglasses"].values()}

        for h in hourglasses:
            if h["is_dead"]:
                continue
            if forced_set is not None and h["id"] not in forced_set:
                continue

            hq, hr = parse_hex(h["position"])
            for nq, nr in hex_neighbors(hq, hr):
                dest_key = hex_key(nq, nr)
                # No other hourglass there
                if dest_key in occupied:
                    continue
                # Not at ring capacity
                space = state["board"][dest_key]
                if len(space["rings"]) >= space["capacity"]:
                    continue
                actions.append({
                    "kind": "move_hourglass",
                    "hourglass_id": h["id"],
                    "to": dest_key,
                })

        return actions

    # ── Play phase: apply actions ────────────────────────

    def _apply_move_hourglass(self, state, player_id, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "move":
            raise ValueError("Not in move phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        hid = action.get("hourglass_id")
        dest = action.get("to")
        if not hid or not dest:
            raise ValueError("Missing hourglass_id or destination")

        h = state["hourglasses"].get(hid)
        if h is None:
            raise ValueError(f"No hourglass with id {hid}")

        player_color = state["players"][player_idx]["color"]
        if h["color"] != player_color:
            raise ValueError("Not your hourglass")
        if h["is_dead"]:
            raise ValueError("That hourglass is dead")

        # Level 2/3: first-3-turns rule
        if state["level"] >= 2:
            moved = state["hourglasses_moved_initial"][player_idx]
            if len(moved) < 3 and hid in moved:
                raise ValueError("Must move a different hourglass in your first 3 turns")

        # Validate destination
        hq, hr = parse_hex(h["position"])
        dq, dr = parse_hex(dest)
        neighbors = hex_neighbors(hq, hr)
        if (dq, dr) not in neighbors:
            raise ValueError("Destination is not adjacent")

        occupied = {hh["position"] for hh in state["hourglasses"].values()}
        if dest in occupied and dest != h["position"]:
            raise ValueError("Destination already has an hourglass")

        space = state["board"][dest]
        if len(space["rings"]) >= space["capacity"]:
            raise ValueError("Destination is at max ring capacity")

        # Check pressure timer penalty before completing the move
        log = []
        self._resolve_pressure_timer(state, player_idx, log)

        # Execute move
        h["position"] = dest
        state["moved_to_space"] = dest

        # Level 2/3: flip the hourglass (sand in bottom becomes new top)
        if state["level"] >= 2:
            now = time.time()
            if h["timer_started_at"] is None:
                # First flip: hourglass was idle, all sand on top → full timer
                h["timer_remaining"] = HOURGLASS_TIMER_SECS
            else:
                # Subsequent flips: sand that fell = TOTAL - current_remaining
                elapsed = now - h["timer_started_at"]
                current = max(0, h["timer_remaining"] - elapsed)
                h["timer_remaining"] = HOURGLASS_TIMER_SECS - current
            h["timer_started_at"] = now

        # Level 2/3: track initial moves
        if state["level"] >= 2:
            moved = state["hourglasses_moved_initial"][player_idx]
            if len(moved) < 3 and hid not in moved:
                moved.append(hid)

        state["consecutive_passes"] = 0

        player_name = state["players"][player_idx]["name"]
        log.append(f"{player_name} moved {hid} to {dest}.")

        # Enter ring window if destination can accept a ring and someone has rings
        space = state["board"][dest]
        any_rings = any(p["rings_remaining"] > 0 for p in state["players"])
        if len(space["rings"]) < space["capacity"] and any_rings:
            state["sub_phase"] = "ring_window"
            state["ring_window_start"] = time.time()
            state["ring_window_space"] = dest
            state["ring_window_mover"] = player_idx
            return ActionResult(state, log=log)

        # No ring window — check bonus rings or advance turn
        return self._maybe_enter_bonus_ring_phase(state, player_idx, log)

    def _apply_place_ring(self, state, player_id, player_idx, action):
        if state["phase"] != "play" or state.get("sub_phase") != "ring_window":
            raise ValueError("Not in ring_window phase")

        space_key = state.get("ring_window_space")
        if not space_key:
            raise ValueError("No space for ring placement")

        # Validate timing: first 3s mover only, after 3s either player
        now = time.time()
        elapsed = now - (state.get("ring_window_start") or now)
        mover_idx = state.get("ring_window_mover")
        if elapsed < 3.0 and player_idx != mover_idx:
            raise ValueError("Ring window: mover has priority for first 3 seconds")

        space = state["board"][space_key]
        player = state["players"][player_idx]

        if len(space["rings"]) >= space["capacity"]:
            raise ValueError("Space is at max capacity")
        if player["rings_remaining"] <= 0:
            raise ValueError("No rings remaining")

        space["rings"].append(player["color"])
        player["rings_remaining"] -= 1

        player_name = player["name"]
        log = [f"{player_name} placed a ring at {space_key}. ({player['rings_remaining']} remaining)"]

        # Clear ring window state
        state["ring_window_start"] = None
        state["ring_window_space"] = None
        state["ring_window_mover"] = None

        # Bonus rings belong to the current player (whose turn it is)
        cp = state["current_player"]
        return self._maybe_enter_bonus_ring_phase(state, cp, log)

    def _apply_pass(self, state, player_id, player_idx):
        if state["phase"] != "play" or state.get("sub_phase") != "move":
            raise ValueError("Not in move phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        # Verify no valid moves
        valid_moves = self._valid_move_actions(state, player_idx)
        if valid_moves:
            raise ValueError("You have valid moves — cannot pass")

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} passed (no valid moves)."]

        state["players"][player_idx]["passed"] = True
        state["consecutive_passes"] += 1

        if state["consecutive_passes"] >= 2:
            return self._end_game(state, log)

        return self._advance_turn(state, log)

    def _maybe_enter_bonus_ring_phase(self, state, player_idx, log):
        """If the player has bonus rings from pressure penalty, enter bonus_ring
        sub-phase so they can choose where to place. Otherwise advance turn."""
        bonus = state["bonus_rings"][player_idx]
        if bonus > 0 and state["players"][player_idx]["rings_remaining"] > 0:
            state["sub_phase"] = "bonus_ring"
            player_name = state["players"][player_idx]["name"]
            log.append(f"{player_name} has {bonus} bonus ring(s) to place (pressure penalty).")
            return ActionResult(state, log=log)
        # No bonus rings — clear any leftover and advance
        state["bonus_rings"][player_idx] = 0
        return self._advance_turn(state, log)

    def _apply_place_bonus_ring(self, state, player_id, player_idx, action):
        """Place a bonus ring on any board space (ignores capacity)."""
        if state["phase"] != "play" or state.get("sub_phase") != "bonus_ring":
            raise ValueError("Not in bonus_ring phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        space_key = action.get("space")
        if not space_key or space_key not in state["board"]:
            raise ValueError("Invalid board space")

        player = state["players"][player_idx]
        if player["rings_remaining"] <= 0:
            raise ValueError("No rings remaining")

        # Bonus rings ignore capacity — can be placed on any space
        space = state["board"][space_key]
        space["rings"].append(player["color"])
        player["rings_remaining"] -= 1
        state["bonus_rings"][player_idx] -= 1

        player_name = player["name"]
        log = [f"{player_name} placed a bonus ring at {space_key}. ({player['rings_remaining']} remaining)"]

        # If more bonus rings remain, stay in bonus_ring phase
        if state["bonus_rings"][player_idx] > 0 and player["rings_remaining"] > 0:
            return ActionResult(state, log=log)

        # Done with bonus rings
        state["bonus_rings"][player_idx] = 0
        return self._advance_turn(state, log)

    def _apply_skip_bonus_ring(self, state, player_id, player_idx):
        """Decline to place remaining bonus ring(s)."""
        if state["phase"] != "play" or state.get("sub_phase") != "bonus_ring":
            raise ValueError("Not in bonus_ring phase")
        if player_idx != state["current_player"]:
            raise ValueError("Not your turn")

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} declined to place bonus ring(s)."]
        state["bonus_rings"][player_idx] = 0
        return self._advance_turn(state, log)

    def _apply_activate_pressure(self, state, player_id, player_idx):
        if state["level"] != 3:
            raise ValueError("Pressure timer only available in Level 3")
        if state["phase"] != "play" or state.get("sub_phase") not in ("move", "ring_window"):
            raise ValueError("Can only activate pressure during opponent's move")
        if player_idx == state["current_player"]:
            raise ValueError("Cannot activate pressure on your own turn")

        pt = state["pressure_timer"]
        now = time.time()

        # Validate: timer must be at zero to flip
        remaining = pt["timer_remaining"]
        if pt["timer_started_at"] is not None:
            remaining = max(0, remaining - (now - pt["timer_started_at"]))
        if remaining > 0:
            raise ValueError("Pressure timer has not fully drained yet")

        # Flip: full 15s, start flowing
        pt["timer_remaining"] = PRESSURE_TIMER_SECS
        pt["timer_started_at"] = now
        pt["active"] = True
        pt["activated_by"] = player_id

        player_name = state["players"][player_idx]["name"]
        log = [f"{player_name} flipped the pressure timer! ({PRESSURE_TIMER_SECS}s)"]
        return ActionResult(state, log=log)

    # ── Turn advancement ─────────────────────────────────

    def _advance_turn(self, state, log):
        state["moved_to_space"] = None
        state["ring_window_start"] = None
        state["ring_window_space"] = None
        state["ring_window_mover"] = None
        state["sub_phase"] = "move"

        # Switch player
        state["current_player"] = 1 - state["current_player"]
        state["turn_number"] += 1
        state["turns_taken"][state["current_player"]] += 1

        # Reset pass state for the new current player
        state["players"][state["current_player"]]["passed"] = False

        # Deactivate pressure timer (sand keeps flowing, but no penalty applies)
        state["pressure_timer"]["active"] = False

        # Check if all rings placed
        if all(p["rings_remaining"] == 0 for p in state["players"]):
            return self._end_game(state, log)

        # Check game over from timers
        game_over = self._check_game_over_from_timers(state, log)
        if game_over:
            return game_over

        # Auto-pass if the new current player has no valid moves.
        # This prevents stalling to bleed opponent timer.
        cp = state["current_player"]
        valid_moves = self._valid_move_actions(state, cp)
        if not valid_moves:
            player_name = state["players"][cp]["name"]
            log.append(f"{player_name} has no valid moves — auto-passed.")
            state["players"][cp]["passed"] = True
            state["consecutive_passes"] += 1

            # Flag so the client can show a notification
            state["auto_passed"] = state["player_ids"][cp]

            if state["consecutive_passes"] >= 2:
                return self._end_game(state, log)

            # Advance to the other player (recursive, but bounded —
            # if both can't move we hit consecutive_passes >= 2 above)
            return self._advance_turn(state, log)

        state["consecutive_passes"] = 0
        state.pop("auto_passed", None)

        return ActionResult(state, log=log)

    # ── Timer logic ──────────────────────────────────────

    def _check_timers(self, state):
        """Update hourglass timers and mark dead ones. Mutates state in place.
        Returns True if game ended due to timer deaths."""
        if state["level"] < 2 or state.get("game_over"):
            return False
        now = time.time()
        for h in state["hourglasses"].values():
            if h["is_dead"] or h["timer_started_at"] is None:
                continue
            elapsed = now - h["timer_started_at"]
            remaining = h["timer_remaining"] - elapsed
            if remaining <= 0:
                h["timer_remaining"] = 0
                h["timer_started_at"] = None
                h["is_dead"] = True
            else:
                h["timer_remaining"] = remaining
                h["timer_started_at"] = now

        # Also update pressure timer (Level 3)
        if state["level"] == 3:
            pt = state["pressure_timer"]
            if pt["timer_started_at"] is not None:
                elapsed = now - pt["timer_started_at"]
                remaining = max(0, pt["timer_remaining"] - elapsed)
                pt["timer_remaining"] = remaining
                if remaining <= 0:
                    pt["timer_started_at"] = None  # sand stopped
                else:
                    pt["timer_started_at"] = now

        # Auto-expire ring window (>6s) so views show correct sub_phase
        if state.get("sub_phase") == "ring_window" and state.get("ring_window_start"):
            rw_elapsed = now - state["ring_window_start"]
            if rw_elapsed >= 6.0:
                state["sub_phase"] = "move"
                state["ring_window_start"] = None
                state["ring_window_space"] = None
                state["ring_window_mover"] = None

        # Check if all of one player's hourglasses are dead → game over
        for pidx in (0, 1):
            color = state["players"][pidx]["color"]
            all_dead = all(
                h["is_dead"] for h in state["hourglasses"].values()
                if h["color"] == color
            )
            if all_dead:
                opp_idx = 1 - pidx
                my_remaining = state["players"][pidx]["rings_remaining"]
                opp_remaining = state["players"][opp_idx]["rings_remaining"]
                # Player with all dead hourglasses and more rings remaining loses
                if my_remaining > opp_remaining:
                    state["game_over"] = True
                    state["phase"] = "game_over"
                    state["sub_phase"] = None
                    state["winner"] = state["players"][opp_idx]["player_id"]
                    return True
                elif my_remaining == opp_remaining:
                    # Check if BOTH players have all dead
                    other_color = state["players"][opp_idx]["color"]
                    other_all_dead = all(
                        h["is_dead"] for h in state["hourglasses"].values()
                        if h["color"] == other_color
                    )
                    if other_all_dead:
                        # Both all dead, tied on rings — draw
                        state["game_over"] = True
                        state["phase"] = "game_over"
                        state["sub_phase"] = None
                        state["winner"] = None
                        return True
                    # Only one player all dead but tied on rings — they still lose
                    # (opponent has surviving hourglasses = tiebreaker)
                    state["game_over"] = True
                    state["phase"] = "game_over"
                    state["sub_phase"] = None
                    state["winner"] = state["players"][opp_idx]["player_id"]
                    return True
        return False

    def _resolve_pressure_timer(self, state, player_idx, log):
        """Check if the pressure timer expired before the player moved.
        Also deactivates the timer (a move was made)."""
        pt = state["pressure_timer"]
        if not pt["active"] or state["level"] != 3:
            return

        now = time.time()
        if pt["timer_started_at"] is not None:
            elapsed = now - pt["timer_started_at"]
            remaining = max(0, pt["timer_remaining"] - elapsed)
            pt["timer_remaining"] = remaining
            # Sand keeps flowing (started_at stays set) — just snapshot it
            pt["timer_started_at"] = now

            if remaining <= 0:
                # Timer fully drained — penalty
                pt["timer_remaining"] = 0
                pt["timer_started_at"] = None  # sand stopped
                opponent_idx = 1 - player_idx
                state["bonus_rings"][opponent_idx] += 1
                opponent_name = state["players"][opponent_idx]["name"]
                log.append(f"Pressure timer expired! {opponent_name} earns a bonus ring.")

        # Move was made — timer is no longer "active" (no penalty applies)
        # but sand keeps flowing if it hasn't drained
        pt["active"] = False

    def _check_game_over_from_timers(self, state, log):
        """Check if all hourglasses of a player are dead."""
        if state["level"] < 2:
            return None

        for pidx in (0, 1):
            color = state["players"][pidx]["color"]
            all_dead = all(
                h["is_dead"] for h in state["hourglasses"].values()
                if h["color"] == color
            )
            if all_dead:
                opp_idx = 1 - pidx
                player_name = state["players"][pidx]["name"]
                opp_name = state["players"][opp_idx]["name"]
                log.append(f"All of {player_name}'s hourglasses are dead.")

                my_remaining = state["players"][pidx]["rings_remaining"]
                opp_remaining = state["players"][opp_idx]["rings_remaining"]

                if my_remaining > opp_remaining:
                    log.append(f"{opp_name} wins! (more rings placed)")
                    state["winner"] = state["players"][opp_idx]["player_id"]
                    return self._end_game(state, log)
                elif my_remaining == opp_remaining:
                    # Tied on rings — opponent has surviving hourglasses
                    opp_color = state["players"][opp_idx]["color"]
                    opp_all_dead = all(
                        h["is_dead"] for h in state["hourglasses"].values()
                        if h["color"] == opp_color
                    )
                    if opp_all_dead:
                        return self._end_game(state, log)
                    log.append(f"{opp_name} wins by tiebreaker (surviving hourglasses).")
                    state["winner"] = state["players"][opp_idx]["player_id"]
                    return self._end_game(state, log)
                else:
                    # Dead player actually placed more rings — they win
                    log.append(f"{player_name} wins! (more rings placed)")
                    state["winner"] = state["players"][pidx]["player_id"]
                    return self._end_game(state, log)

        return None

    # ── Game end ─────────────────────────────────────────

    def _end_game(self, state, log):
        state["game_over"] = True
        state["phase"] = "game_over"
        state["sub_phase"] = None

        p0 = state["players"][0]
        p1 = state["players"][1]

        r0 = p0["rings_remaining"]
        r1 = p1["rings_remaining"]

        log.append(f"Game over! {p0['name']}: {RINGS_PER_PLAYER - r0} rings placed, "
                   f"{p1['name']}: {RINGS_PER_PLAYER - r1} rings placed.")

        if r0 < r1:
            state["winner"] = p0["player_id"]
            log.append(f"{p0['name']} wins!")
        elif r1 < r0:
            state["winner"] = p1["player_id"]
            log.append(f"{p1['name']} wins!")
        else:
            # Tiebreaker for Level 2/3: player with a surviving hourglass
            if state["level"] >= 2:
                winner = self._tiebreak_by_hourglasses(state)
                if winner is not None:
                    state["winner"] = state["players"][winner]["player_id"]
                    log.append(f"{state['players'][winner]['name']} wins the tiebreaker "
                               f"(surviving hourglass)!")
                else:
                    state["winner"] = None
                    log.append("It's a draw!")
            else:
                state["winner"] = None
                log.append("It's a draw!")

        return ActionResult(state, log=log, game_over=True)

    def _tiebreak_by_hourglasses(self, state):
        """Returns player index who has a surviving hourglass, or None if tied."""
        surviving = [False, False]
        for h in state["hourglasses"].values():
            if not h["is_dead"]:
                idx = 0 if h["color"] == "black" else 1
                surviving[idx] = True

        if surviving[0] and not surviving[1]:
            return 0
        elif surviving[1] and not surviving[0]:
            return 1
        return None

    # ── Helpers ──────────────────────────────────────────

    def _player_index(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None
