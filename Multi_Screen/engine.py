"""
In the Year of the Dragon — game engine implementation.

Implements the GameEngine interface as a pure state machine.
All state is a plain dict. No side effects, no networking.
"""

from copy import deepcopy

from server.game_engine import GameEngine, ActionResult
from server.dragon.state import (
    PERSON_TYPES, ACTION_INFO, ACTION_IDS, EVENT_TYPES, PLAYER_COLORS,
    count_symbols, get_person_track_order, combo_key,
    generate_event_tiles, generate_person_tiles, create_player, deal_action_groups,
    execute_taxes, execute_harvest, execute_fireworks, execute_military,
    execute_research, execute_build, execute_build_auto, execute_privilege,
    apply_decay,
)


class DragonEngine(GameEngine):

    # ── Setup ────────────────────────────────────────────────────────

    def initial_state(self, player_ids, player_names):
        player_count = len(player_ids)
        if player_count < 2 or player_count > 5:
            raise ValueError("Dragon requires 2-5 players")

        players = []
        for i, (pid, name) in enumerate(zip(player_ids, player_names)):
            players.append(create_player(i, pid, name))

        events = generate_event_tiles()
        tiles = generate_person_tiles(player_count)

        return {
            "game": "dragon",
            "player_count": player_count,
            "player_ids": list(player_ids),
            "players": players,
            "events": events,
            "remaining_tiles": tiles,
            "current_round": 0,

            # Phase machine
            "phase": "draft",
            "sub_phase": None,

            # Draft state
            "draft": {
                "current_drafter": 0,  # index into players
                "used_combos": [],     # list of combo_key strings
            },

            # Action phase state
            "action": {
                "order_idx": 0,
                "turn_order": [],
                "action_groups": [],
                "dragons": [],  # per-group list of player indices who chose it
            },

            # Person phase state
            "person": {
                "order_idx": 0,
                "turn_order": [],
            },

            # Event phase state
            "event": {
                "resolved": False,
                "log": [],
                # Release queue for tribute/contagion/mongols
                "release_queue": [],   # [{player_idx, count, reason}]
                # Drought queue
                "drought_queue": [],   # [{player_idx, phase: "feed"|"release", unfed_palaces: [...]}]
            },

            # Scoring phase state
            "scoring": {
                "scored": False,
                "details": [],
            },

            # Game log
            "log": [],
        }

    # ── Player View ──────────────────────────────────────────────────

    def get_player_view(self, state, player_id):
        """
        Dragon is mostly open information — everyone can see everything.
        The only hidden info is other players' cards (hand).
        We return the full state but redact other players' hands.
        """
        view = deepcopy(state)

        # Remove internal tile pool from view (players shouldn't see upcoming tiles)
        # Actually in the board game the tiles are face-up, so keep remaining_tiles visible

        for p in view["players"]:
            if p["player_id"] != player_id:
                # Show card count but not contents
                p["cards"] = [{"hidden": True} for _ in p["cards"]]

        view["your_player_id"] = player_id
        view["your_player_idx"] = self._player_idx(state, player_id)
        view["valid_actions"] = self.get_valid_actions(state, player_id)

        return view

    # ── Waiting For ──────────────────────────────────────────────────

    def get_waiting_for(self, state):
        phase = state["phase"]

        if phase == "draft":
            idx = state["draft"]["current_drafter"]
            return [state["players"][idx]["player_id"]]

        if phase == "action":
            a = state["action"]
            if a["order_idx"] < len(a["turn_order"]):
                pidx = a["turn_order"][a["order_idx"]]
                return [state["players"][pidx]["player_id"]]
            return []

        if phase == "person":
            p = state["person"]
            if p["order_idx"] < len(p["turn_order"]):
                pidx = p["turn_order"][p["order_idx"]]
                return [state["players"][pidx]["player_id"]]
            return []

        if phase == "event":
            ev = state["event"]
            if not ev["resolved"]:
                # Check drought queue
                if ev["drought_queue"]:
                    dq = ev["drought_queue"][0]
                    return [state["players"][dq["player_idx"]]["player_id"]]
                # Check release queue
                if ev["release_queue"]:
                    rq = ev["release_queue"][0]
                    return [state["players"][rq["player_idx"]]["player_id"]]
                # Need someone to click "resolve" — any player can
                return list(state["player_ids"])
            return []

        if phase == "scoring":
            # Any player can trigger scoring / advance to next round
            return list(state["player_ids"])

        if phase == "final":
            return []

        return []

    # ── Phase Info ───────────────────────────────────────────────────

    def get_phase_info(self, state):
        phase = state["phase"]
        info = {
            "phase": phase,
            "round": state["current_round"],
            "round_display": state["current_round"] + 1,
            "total_rounds": 12,
        }

        if phase == "draft":
            drafter = state["players"][state["draft"]["current_drafter"]]
            info["description"] = f"{drafter['name']} is drafting starting courtiers"
        elif phase == "action":
            a = state["action"]
            if a["order_idx"] < len(a["turn_order"]):
                p = state["players"][a["turn_order"][a["order_idx"]]]
                info["description"] = f"{p['name']} is choosing an action"
            else:
                info["description"] = "Action phase complete"
        elif phase == "person":
            p_state = state["person"]
            if p_state["order_idx"] < len(p_state["turn_order"]):
                p = state["players"][p_state["turn_order"][p_state["order_idx"]]]
                info["description"] = f"{p['name']} is placing a person"
            else:
                info["description"] = "Person phase complete"
        elif phase == "event":
            ev = state["events"][state["current_round"]]
            info["description"] = f"Event: {ev['name']}"
            info["event"] = ev
        elif phase == "scoring":
            info["description"] = "Scoring phase"
        elif phase == "final":
            info["description"] = "Game over — final scoring"

        return info

    # ── Valid Actions ────────────────────────────────────────────────

    def get_valid_actions(self, state, player_id):
        pidx = self._player_idx(state, player_id)
        if pidx is None:
            return []

        phase = state["phase"]

        if phase == "draft":
            return self._valid_draft_actions(state, pidx)
        if phase == "action":
            return self._valid_action_actions(state, pidx)
        if phase == "person":
            return self._valid_person_actions(state, pidx)
        if phase == "event":
            return self._valid_event_actions(state, pidx)
        if phase == "scoring":
            return self._valid_scoring_actions(state, pidx)

        return []

    # ── Apply Action ─────────────────────────────────────────────────

    def apply_action(self, state, player_id, action):
        pidx = self._player_idx(state, player_id)
        if pidx is None:
            raise ValueError("Unknown player")

        phase = state["phase"]
        kind = action.get("kind")

        new_state = deepcopy(state)

        if phase == "draft" and kind == "draft_pick":
            return self._apply_draft(new_state, pidx, action)
        if phase == "action" and kind == "choose_action":
            return self._apply_action_choice(new_state, pidx, action)
        if phase == "action" and kind == "confirm_build":
            return self._apply_build_confirm(new_state, pidx, action)
        if phase == "action" and kind == "skip_action":
            return self._apply_skip(new_state, pidx)
        if phase == "person" and kind == "play_person":
            return self._apply_person(new_state, pidx, action)
        if phase == "event" and kind == "resolve_event":
            result = self._apply_resolve_event(new_state, pidx)
            self._check_event_finished(result.new_state)
            return result
        if phase == "event" and kind == "feed_palaces":
            result = self._apply_feed(new_state, pidx, action)
            self._check_event_finished(result.new_state)
            return result
        if phase == "event" and kind == "release_person":
            result = self._apply_release(new_state, pidx, action)
            self._check_event_finished(result.new_state)
            return result
        if phase == "scoring" and kind == "score":
            return self._apply_scoring(new_state, pidx)
        if phase == "scoring" and kind == "next_round":
            return self._apply_next_round(new_state, pidx)

        raise ValueError(f"Invalid action kind '{kind}' for phase '{phase}'")

    # ── DRAFT ────────────────────────────────────────────────────────

    def _valid_draft_actions(self, state, pidx):
        if pidx != state["draft"]["current_drafter"]:
            return []

        player = state["players"][pidx]
        tiles = state["remaining_tiles"]
        used = set(state["draft"]["used_combos"])

        # Only young tiles available for draft
        young_tiles = [t for t in tiles if t["experience"] == "young"]

        # Group by type to show available types
        available_types = {}
        for t in young_tiles:
            if t["type_id"] not in available_types:
                available_types[t["type_id"]] = t

        return [{
            "kind": "draft_pick",
            "description": "Pick 2 different young courtiers for your starting palaces",
            "available_types": list(available_types.keys()),
            "forbidden_combos": list(used),
        }]

    def _apply_draft(self, state, pidx, action):
        if pidx != state["draft"]["current_drafter"]:
            raise ValueError("Not your turn to draft")

        picks = action.get("picks", [])
        if len(picks) != 2:
            raise ValueError("Must pick exactly 2 courtiers")

        type_a, type_b = picks[0], picks[1]
        if type_a == type_b:
            raise ValueError("Must pick 2 different types")

        ck = combo_key(type_a, type_b)
        if ck in state["draft"]["used_combos"]:
            raise ValueError(f"Combination {ck} already used")

        # Find tiles in pool
        tiles = state["remaining_tiles"]
        found = [None, None]
        for pick_idx, type_id in enumerate(picks):
            for i, t in enumerate(tiles):
                if t["type_id"] == type_id and t["experience"] == "young":
                    found[pick_idx] = i
                    break
            if found[pick_idx] is None:
                raise ValueError(f"No young {type_id} tile available")

        # Remove tiles from pool (remove higher index first to avoid shift)
        tile_a = tiles[found[0]]
        tile_b = tiles[found[1]]
        indices_to_remove = sorted(found, reverse=True)
        for idx in indices_to_remove:
            tiles.pop(idx)

        # Place in player's palaces
        player = state["players"][pidx]
        player["palaces"][0]["persons"] = [tile_a]
        player["palaces"][1]["persons"] = [tile_b]
        player["person_track"] = tile_a["value"] + tile_b["value"]

        state["draft"]["used_combos"].append(ck)

        log = [f"{player['name']} drafted {PERSON_TYPES[type_a]['name']} and {PERSON_TYPES[type_b]['name']}"]

        # Advance to next drafter or start game
        next_drafter = pidx + 1
        if next_drafter >= state["player_count"]:
            # Draft complete — start round 1
            state["phase"] = "action"
            state["draft"]["current_drafter"] = None
            self._setup_action_phase(state)
            log.append("Draft complete! Starting Round 1.")
        else:
            state["draft"]["current_drafter"] = next_drafter

        return ActionResult(new_state=state, log=log)

    # ── ACTION PHASE ─────────────────────────────────────────────────

    def _setup_action_phase(self, state):
        players = state["players"]
        order = get_person_track_order(players)
        groups = deal_action_groups(state["player_count"])
        state["action"] = {
            "order_idx": 0,
            "turn_order": order,
            "action_groups": groups,
            "dragons": [[] for _ in groups],
        }

    def _valid_action_actions(self, state, pidx):
        a = state["action"]
        if a["order_idx"] >= len(a["turn_order"]):
            return []
        if pidx != a["turn_order"][a["order_idx"]]:
            return []

        # If we're in a build sub-phase, only allow confirm_build
        if state["sub_phase"] == "awaiting_build":
            player = state["players"][pidx]
            bonus = count_symbols(player, "craftsman")
            total_floors = 1 + bonus
            return [{
                "kind": "confirm_build",
                "description": f"Place {total_floors} floor(s) on your palaces",
                "total_floors": total_floors,
                "palaces": player["palaces"],
            }]

        player = state["players"][pidx]
        groups = a["action_groups"]
        dragons = a["dragons"]

        available_groups = []
        for g_idx, group in enumerate(groups):
            cost = 3 if len(dragons[g_idx]) > 0 else 0
            can_afford = player["yuan"] >= cost
            available_groups.append({
                "group_index": g_idx,
                "actions": group,
                "dragon_count": len(dragons[g_idx]),
                "cost": cost,
                "can_afford": can_afford,
            })

        actions = [{
            "kind": "choose_action",
            "description": "Choose an action group and action",
            "groups": available_groups,
            "player_yuan": player["yuan"],
        }]

        # Can always skip
        actions.append({
            "kind": "skip_action",
            "description": "Skip (top up to 3¥)",
        })

        return actions

    def _apply_action_choice(self, state, pidx, action):
        a = state["action"]
        if a["order_idx"] >= len(a["turn_order"]):
            raise ValueError("Action phase complete")
        if pidx != a["turn_order"][a["order_idx"]]:
            raise ValueError("Not your turn")
        if state["sub_phase"] == "awaiting_build":
            raise ValueError("Must confirm build placement first")

        group_idx = action.get("group_index")
        action_id = action.get("action_id")

        if group_idx is None or action_id is None:
            raise ValueError("Must specify group_index and action_id")
        if group_idx < 0 or group_idx >= len(a["action_groups"]):
            raise ValueError("Invalid group index")
        if action_id not in a["action_groups"][group_idx]:
            raise ValueError(f"Action {action_id} not in group {group_idx}")

        player = state["players"][pidx]
        dragons = a["dragons"]
        cost = 3 if len(dragons[group_idx]) > 0 else 0

        if player["yuan"] < cost:
            raise ValueError(f"Not enough yuan (need {cost}, have {player['yuan']})")

        # Pay dragon cost
        if cost > 0:
            player["yuan"] -= cost

        # Record dragon
        dragons[group_idx].append(pidx)

        log = []
        if cost > 0:
            log.append(f"{player['name']} paid {cost}¥ for occupied group.")

        # Build is special — needs placement input
        if action_id == "build":
            state["sub_phase"] = "awaiting_build"
            state["action"]["_build_cost_paid"] = cost
            log.append(f"{player['name']} chose Build — awaiting placement.")
            return ActionResult(new_state=state, log=log)

        # Execute action
        if action_id == "privilege":
            size = action.get("privilege_size")
            if size not in ("small", "large"):
                raise ValueError("Must specify privilege_size: 'small' or 'large'")
            # Check affordability after dragon cost
            needed = 2 if size == "small" else 7
            if player["yuan"] < needed:
                raise ValueError(f"Not enough yuan for {size} privilege")
            msg = execute_privilege(player, size)
        else:
            msg = {
                "taxes": execute_taxes,
                "harvest": execute_harvest,
                "fireworks": execute_fireworks,
                "military": execute_military,
                "research": execute_research,
            }[action_id](player)

        log.append(f"{player['name']}: {msg}")
        self._advance_action_turn(state)

        return ActionResult(new_state=state, log=log)

    def _apply_build_confirm(self, state, pidx, action):
        if state["sub_phase"] != "awaiting_build":
            raise ValueError("Not in build sub-phase")
        a = state["action"]
        if pidx != a["turn_order"][a["order_idx"]]:
            raise ValueError("Not your turn")

        player = state["players"][pidx]
        placement = action.get("placement", [])

        msg = execute_build(player, placement)
        log = [f"{player['name']}: {msg}"]

        state["sub_phase"] = None
        if "_build_cost_paid" in state["action"]:
            del state["action"]["_build_cost_paid"]

        self._advance_action_turn(state)
        return ActionResult(new_state=state, log=log)

    def _apply_skip(self, state, pidx):
        a = state["action"]
        if a["order_idx"] >= len(a["turn_order"]):
            raise ValueError("Action phase complete")
        if pidx != a["turn_order"][a["order_idx"]]:
            raise ValueError("Not your turn")

        player = state["players"][pidx]
        need = max(0, 3 - player["yuan"])
        player["yuan"] += need

        log = [f"{player['name']} skipped. Took {need}¥ (now {player['yuan']}¥)."]
        self._advance_action_turn(state)
        return ActionResult(new_state=state, log=log)

    def _advance_action_turn(self, state):
        a = state["action"]
        a["order_idx"] += 1
        if a["order_idx"] >= len(a["turn_order"]):
            # Action phase done — move to person phase (or event if round >= 11)
            if state["current_round"] >= 11:
                state["phase"] = "event"
                self._setup_event_phase(state)
            else:
                state["phase"] = "person"
                self._setup_person_phase(state)

    # ── PERSON PHASE ─────────────────────────────────────────────────

    def _setup_person_phase(self, state):
        order = get_person_track_order(state["players"])
        state["person"] = {
            "order_idx": 0,
            "turn_order": order,
        }

    def _valid_person_actions(self, state, pidx):
        p = state["person"]
        if p["order_idx"] >= len(p["turn_order"]):
            return []
        if pidx != p["turn_order"][p["order_idx"]]:
            return []

        player = state["players"][pidx]
        tiles = state["remaining_tiles"]

        # Available cards
        cards_info = []
        for i, card in enumerate(player["cards"]):
            if card["is_wild"]:
                matching = tiles  # wild matches all
            else:
                matching = [t for t in tiles if t["type_id"] == card["type_id"]]
            cards_info.append({
                "card_index": i,
                "type_id": card["type_id"],
                "is_wild": card["is_wild"],
                "matching_tile_count": len(matching),
            })

        # Palace info for placement
        palaces_info = []
        has_empty_slot = False
        all_full = True
        for i, pal in enumerate(player["palaces"]):
            is_full = len(pal["persons"]) >= pal["floors"]
            if not is_full:
                has_empty_slot = True
                all_full = False
            palaces_info.append({
                "palace_index": i,
                "floors": pal["floors"],
                "person_count": len(pal["persons"]),
                "is_full": is_full,
            })

        return [{
            "kind": "play_person",
            "description": "Play a person card and place a courtier",
            "cards": cards_info,
            "palaces": palaces_info,
            "has_empty_slot": has_empty_slot,
            "all_full": all_full,
        }]

    def _apply_person(self, state, pidx, action):
        p_state = state["person"]
        if p_state["order_idx"] >= len(p_state["turn_order"]):
            raise ValueError("Person phase complete")
        if pidx != p_state["turn_order"][p_state["order_idx"]]:
            raise ValueError("Not your turn")

        player = state["players"][pidx]
        card_index = action.get("card_index")
        tile_id = action.get("tile_id")  # None if no tiles available
        palace_index = action.get("palace_index")  # None if releasing immediately
        replace_index = action.get("replace_index")  # index of person to replace in palace
        release_immediately = action.get("release_immediately", False)

        if card_index is None or card_index < 0 or card_index >= len(player["cards"]):
            raise ValueError("Invalid card index")

        card = player["cards"][card_index]
        tiles = state["remaining_tiles"]

        # Determine matching tiles
        if card["is_wild"]:
            matching = tiles
        else:
            matching = [t for t in tiles if t["type_id"] == card["type_id"]]

        log = []

        # Remove card from hand
        player["cards"].pop(card_index)
        card_name = "Wild" if card["is_wild"] else PERSON_TYPES[card["type_id"]]["name"]
        log.append(f"{player['name']} played {card_name} card.")

        if not matching:
            log.append("No matching tiles available — card discarded.")
            self._advance_person_turn(state)
            return ActionResult(new_state=state, log=log)

        # Find the tile
        if tile_id is None:
            raise ValueError("Must specify tile_id when tiles are available")

        tile = None
        tile_pool_idx = None
        for i, t in enumerate(tiles):
            if t["id"] == tile_id:
                # Verify it matches the card
                if not card["is_wild"] and t["type_id"] != card["type_id"]:
                    raise ValueError("Tile doesn't match card type")
                tile = t
                tile_pool_idx = i
                break

        if tile is None:
            raise ValueError(f"Tile {tile_id} not found in pool")

        # Remove tile from pool
        tiles.pop(tile_pool_idx)

        tile_type = PERSON_TYPES[tile["type_id"]]

        if release_immediately:
            log.append(f"{player['name']} released {tile_type['name']} immediately (no placement).")
            self._advance_person_turn(state)
            return ActionResult(new_state=state, log=log)

        # Place tile
        if palace_index is None:
            raise ValueError("Must specify palace_index for placement")
        if palace_index < 0 or palace_index >= len(player["palaces"]):
            raise ValueError("Invalid palace index")

        palace = player["palaces"][palace_index]
        has_empty_anywhere = any(
            len(pal["persons"]) < pal["floors"] for pal in player["palaces"]
        )

        if len(palace["persons"]) < palace["floors"]:
            # Has space — just add
            palace["persons"].append(tile)
            player["person_track"] += tile["value"]
            log.append(f"{player['name']} placed {tile_type['name']} in Palace {palace_index + 1} (+{tile['value']} person track).")
        elif has_empty_anywhere:
            raise ValueError("Must place in a palace with empty slots first")
        else:
            # All palaces full — must replace
            if replace_index is None:
                raise ValueError("All palaces full — must specify replace_index")
            if replace_index < 0 or replace_index >= len(palace["persons"]):
                raise ValueError("Invalid replace index")

            replaced = palace["persons"][replace_index]
            replaced_type = PERSON_TYPES[replaced["type_id"]]
            palace["persons"][replace_index] = tile
            player["person_track"] += tile["value"]
            log.append(
                f"{player['name']} replaced {replaced_type['name']} with {tile_type['name']} "
                f"in Palace {palace_index + 1} (+{tile['value']} person track)."
            )

        self._advance_person_turn(state)
        return ActionResult(new_state=state, log=log)

    def _advance_person_turn(self, state):
        p = state["person"]
        p["order_idx"] += 1
        if p["order_idx"] >= len(p["turn_order"]):
            state["phase"] = "event"
            self._setup_event_phase(state)

    # ── EVENT PHASE ──────────────────────────────────────────────────

    def _setup_event_phase(self, state):
        state["event"] = {
            "resolved": False,
            "log": [],
            "release_queue": [],
            "drought_queue": [],
        }

    def _finish_event(self, state):
        """Auto-transition from resolved event to scoring phase."""
        state["phase"] = "scoring"
        state["scoring"] = {"scored": False, "details": []}

    def _check_event_finished(self, state):
        """If the event is fully resolved, auto-advance to scoring."""
        if state["phase"] == "event" and state["event"]["resolved"]:
            self._finish_event(state)

    def _valid_event_actions(self, state, pidx):
        ev = state["event"]
        event_tile = state["events"][state["current_round"]]

        # Not yet resolved — need "resolve" trigger
        if not ev["resolved"] and not ev["release_queue"] and not ev["drought_queue"] and not ev["log"]:
            # Any player can trigger (but typically first player)
            return [{"kind": "resolve_event", "description": f"Resolve {event_tile['name']}"}]

        # Drought feeding
        if ev["drought_queue"]:
            dq = ev["drought_queue"][0]
            if dq["player_idx"] != pidx:
                return []

            if dq["phase"] == "feed":
                player = state["players"][pidx]
                inhabited = [
                    {"palace_index": i, "person_count": len(pal["persons"])}
                    for i, pal in enumerate(player["palaces"])
                    if len(pal["persons"]) > 0
                ]
                max_feed = min(player["rice"], len(inhabited))
                return [{
                    "kind": "feed_palaces",
                    "description": "Choose which palaces to feed",
                    "rice_available": player["rice"],
                    "inhabited_palaces": inhabited,
                    "must_feed": max_feed,
                }]

            if dq["phase"] == "release":
                palace_idx = dq["unfed_palaces"][0]
                player = state["players"][pidx]
                persons = player["palaces"][palace_idx]["persons"]
                return [{
                    "kind": "release_person",
                    "description": f"Release 1 courtier from Palace {palace_idx + 1}",
                    "palace_index": palace_idx,
                    "persons": [
                        {"person_index": i, "type_id": per["type_id"], "name": PERSON_TYPES[per["type_id"]]["name"]}
                        for i, per in enumerate(persons)
                    ],
                    "reason": "drought",
                }]

        # Generic release (tribute, contagion, mongols)
        if ev["release_queue"]:
            rq = ev["release_queue"][0]
            if rq["player_idx"] != pidx:
                return []

            player = state["players"][pidx]
            persons = []
            for pal_idx, pal in enumerate(player["palaces"]):
                for per_idx, per in enumerate(pal["persons"]):
                    persons.append({
                        "palace_index": pal_idx,
                        "person_index": per_idx,
                        "type_id": per["type_id"],
                        "name": PERSON_TYPES[per["type_id"]]["name"],
                    })
            return [{
                "kind": "release_person",
                "description": f"Release 1 courtier ({rq['reason']}) — {rq['count']} remaining",
                "persons": persons,
                "reason": rq["reason"],
                "count_remaining": rq["count"],
            }]

        # Event fully resolved — auto-transitions to scoring via _check_event_finished
        return []

    def _apply_resolve_event(self, state, pidx):
        ev = state["event"]
        event_tile = state["events"][state["current_round"]]
        players = state["players"]
        log = ev["log"]
        releases = []

        eid = event_tile["id"]

        if eid == "peace":
            log.append("Peace reigns. Nothing happens.")
            apply_decay(players, log)
            ev["resolved"] = True
            return ActionResult(new_state=state, log=log)

        if eid == "imperialTribute":
            for i, p in enumerate(players):
                if p["yuan"] >= 4:
                    p["yuan"] -= 4
                    log.append(f"{p['name']} pays 4¥.")
                else:
                    shortfall = 4 - p["yuan"]
                    p["yuan"] = 0
                    log.append(f"{p['name']} pays {4 - shortfall}¥, releases {shortfall}.")
                    releases.append({"player_idx": i, "count": shortfall, "reason": "Tribute"})

        elif eid == "drought":
            dq = []
            for i, p in enumerate(players):
                inhabited = [j for j, pal in enumerate(p["palaces"]) if len(pal["persons"]) > 0]
                if not inhabited:
                    log.append(f"{p['name']} has no inhabited palaces.")
                    continue
                if p["rice"] == 0:
                    log.append(f"{p['name']} has no rice — all {len(inhabited)} palace(s) unfed.")
                    dq.append({"player_idx": i, "phase": "release", "unfed_palaces": inhabited})
                else:
                    dq.append({"player_idx": i, "phase": "feed"})

            if dq:
                ev["drought_queue"] = dq
            else:
                apply_decay(players, log)
                ev["resolved"] = True

            return ActionResult(new_state=state, log=log)

        elif eid == "contagion":
            for i, p in enumerate(players):
                healers = count_symbols(p, "healer")
                lose = max(0, 3 - healers)
                total_persons = sum(len(pal["persons"]) for pal in p["palaces"])
                actual = min(lose, total_persons)
                if actual > 0:
                    log.append(f"{p['name']} releases {actual} (3-{healers} healers).")
                    releases.append({"player_idx": i, "count": actual, "reason": "Contagion"})
                else:
                    log.append(f"{p['name']} protected.")

        elif eid == "mongolInvasion":
            helmet_counts = []
            min_helmets = float("inf")
            for i, p in enumerate(players):
                h = count_symbols(p, "warrior")
                helmet_counts.append(h)
                p["scoring_track"] += h
                log.append(f"{p['name']} +{h} VP (warriors).")
                if h < min_helmets:
                    min_helmets = h

            for i, h in enumerate(helmet_counts):
                if h == min_helmets:
                    has_persons = any(len(pal["persons"]) > 0 for pal in players[i]["palaces"])
                    if has_persons:
                        log.append(f"{players[i]['name']} fewest ({h}), releases 1.")
                        releases.append({"player_idx": i, "count": 1, "reason": "Mongols"})

        elif eid == "dragonFestival":
            fw = [p["fireworks"] for p in players]
            m1 = max(fw) if fw else 0
            m2 = max((f for f in fw if f < m1), default=-1)

            for i, p in enumerate(players):
                if p["fireworks"] > 0 and p["fireworks"] == m1:
                    p["scoring_track"] += 6
                    ret = (p["fireworks"] + 1) // 2  # ceil
                    p["fireworks"] -= ret
                    log.append(f"{p['name']} wins! +6 VP, returns {ret}.")
                elif p["fireworks"] > 0 and m2 > 0 and p["fireworks"] == m2:
                    p["scoring_track"] += 3
                    ret = (p["fireworks"] + 1) // 2
                    p["fireworks"] -= ret
                    log.append(f"{p['name']} 2nd! +3 VP, returns {ret}.")

        # Set up release queue if needed
        if releases:
            ev["release_queue"] = releases
        else:
            apply_decay(players, log)
            ev["resolved"] = True

        return ActionResult(new_state=state, log=log)

    def _apply_feed(self, state, pidx, action):
        ev = state["event"]
        if not ev["drought_queue"]:
            raise ValueError("No drought to resolve")

        dq = ev["drought_queue"][0]
        if dq["player_idx"] != pidx or dq["phase"] != "feed":
            raise ValueError("Not your turn to feed")

        player = state["players"][pidx]
        fed_palaces = set(action.get("fed_palaces", []))

        inhabited = [i for i, pal in enumerate(player["palaces"]) if len(pal["persons"]) > 0]
        max_feed = min(player["rice"], len(inhabited))

        if len(fed_palaces) != max_feed:
            raise ValueError(f"Must feed exactly {max_feed} palaces")

        for pi in fed_palaces:
            if pi not in inhabited:
                raise ValueError(f"Palace {pi} is not inhabited")

        player["rice"] -= len(fed_palaces)
        log = ev["log"]
        log.append(f"{player['name']} feeds {len(fed_palaces)} palace(s) ({player['rice']} rice left).")

        unfed = [i for i in inhabited if i not in fed_palaces]
        if unfed:
            log.append(f"{player['name']} has {len(unfed)} unfed palace(s) — must release 1 person from each.")
            ev["drought_queue"][0] = {"player_idx": pidx, "phase": "release", "unfed_palaces": unfed}
        else:
            self._advance_drought_queue(state)

        return ActionResult(new_state=state, log=log)

    def _apply_release(self, state, pidx, action):
        ev = state["event"]

        # Drought release
        if ev["drought_queue"]:
            dq = ev["drought_queue"][0]
            if dq["player_idx"] != pidx or dq["phase"] != "release":
                raise ValueError("Not your turn to release")

            palace_idx = dq["unfed_palaces"][0]
            person_index = action.get("person_index")

            player = state["players"][pidx]
            palace = player["palaces"][palace_idx]

            if person_index is None or person_index < 0 or person_index >= len(palace["persons"]):
                raise ValueError("Invalid person index")

            released = palace["persons"].pop(person_index)
            name = PERSON_TYPES[released["type_id"]]["name"]
            log = ev["log"]
            log.append(f"{player['name']} releases {name} from Palace {palace_idx + 1}.")

            remaining_unfed = dq["unfed_palaces"][1:]
            if remaining_unfed:
                ev["drought_queue"][0] = {**dq, "unfed_palaces": remaining_unfed}
            else:
                self._advance_drought_queue(state)

            return ActionResult(new_state=state, log=log)

        # Generic release (tribute, contagion, mongols)
        if ev["release_queue"]:
            rq = ev["release_queue"][0]
            if rq["player_idx"] != pidx:
                raise ValueError("Not your turn to release")

            palace_index = action.get("palace_index")
            person_index = action.get("person_index")

            player = state["players"][pidx]
            if palace_index is None or palace_index < 0 or palace_index >= len(player["palaces"]):
                raise ValueError("Invalid palace index")

            palace = player["palaces"][palace_index]
            if person_index is None or person_index < 0 or person_index >= len(palace["persons"]):
                raise ValueError("Invalid person index")

            released = palace["persons"].pop(person_index)
            name = PERSON_TYPES[released["type_id"]]["name"]
            log = ev["log"]
            log.append(f"{player['name']} releases {name} from Palace {palace_index + 1} ({rq['reason']}).")

            rq["count"] -= 1
            if rq["count"] <= 0:
                ev["release_queue"].pop(0)

            if not ev["release_queue"]:
                apply_decay(state["players"], log)
                ev["resolved"] = True

            return ActionResult(new_state=state, log=log)

        raise ValueError("No active release requirement")

    def _advance_drought_queue(self, state):
        ev = state["event"]
        ev["drought_queue"].pop(0)
        if not ev["drought_queue"]:
            apply_decay(state["players"], ev["log"])
            ev["resolved"] = True

    # ── SCORING PHASE ────────────────────────────────────────────────

    def _valid_scoring_actions(self, state, pidx):
        sc = state["scoring"]
        if not sc["scored"]:
            return [{"kind": "score", "description": "Calculate round scores"}]
        else:
            if state["current_round"] < 11:
                return [{"kind": "next_round", "description": "Start next round"}]
            else:
                return [{"kind": "next_round", "description": "Final scoring"}]

    def _apply_scoring(self, state, pidx):
        sc = state["scoring"]
        if sc["scored"]:
            raise ValueError("Already scored this round")

        players = state["players"]
        details = []
        log = []

        for i, p in enumerate(players):
            palace_pts = len(p["palaces"])
            ladies = 0
            for pal in p["palaces"]:
                for per in pal["persons"]:
                    if per["type_id"] == "courtLady":
                        ladies += per["symbols"]
            priv = p["privileges"]["small"] + p["privileges"]["large"] * 2
            total = palace_pts + ladies + priv
            p["scoring_track"] += total
            d = {"player_idx": i, "palaces": palace_pts, "ladies": ladies, "privileges": priv, "total": total}
            details.append(d)
            log.append(f"{p['name']}: +{total} VP ({palace_pts} palaces, {ladies} ladies, {priv} privileges)")

        sc["scored"] = True
        sc["details"] = details

        return ActionResult(new_state=state, log=log)

    def _apply_next_round(self, state, pidx):
        current = state["current_round"] + 1

        if current >= 12:
            # Final scoring
            return self._do_final_scoring(state)

        state["current_round"] = current
        state["phase"] = "action"
        state["sub_phase"] = None
        state["scoring"] = {"scored": False, "details": []}

        self._setup_action_phase(state)

        return ActionResult(
            new_state=state,
            log=[f"Round {current + 1} begins!"],
        )

    def _do_final_scoring(self, state):
        state["phase"] = "final"
        players = state["players"]
        log = ["=== FINAL SCORING ==="]
        results = []

        for p in players:
            person_pts = 0
            monk_pts = 0
            for pal in p["palaces"]:
                for per in pal["persons"]:
                    person_pts += 2
                    if per["type_id"] == "monk":
                        monk_pts += per["symbols"] * pal["floors"]

            sale = (p["rice"] + p["fireworks"]) * 2
            money_pts = (p["yuan"] + sale) // 3
            final = p["scoring_track"] + person_pts + monk_pts + money_pts

            results.append({
                "player_idx": p["index"],
                "name": p["name"],
                "game_score": p["scoring_track"],
                "person_pts": person_pts,
                "monk_pts": monk_pts,
                "money_pts": money_pts,
                "final_score": final,
                "person_track": p["person_track"],
            })
            log.append(
                f"{p['name']}: {final} VP "
                f"(game {p['scoring_track']} + persons {person_pts} + monks {monk_pts} + money {money_pts})"
            )

        results.sort(key=lambda r: (r["final_score"], r["person_track"]), reverse=True)
        state["final_results"] = results
        log.append(f"Winner: {results[0]['name']} with {results[0]['final_score']} VP!")

        return ActionResult(new_state=state, log=log, game_over=True)

    # ── Helpers ───────────────────────────────────────────────────────

    def _player_idx(self, state, player_id):
        for i, p in enumerate(state["players"]):
            if p["player_id"] == player_id:
                return i
        return None
