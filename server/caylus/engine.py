"""
Caylus game engine — full implementation of the board game.

7 phases per round: Income → Workers → Special Buildings → Provost →
Activate Buildings → Castle → End Turn.

All state uses player indices (0-based) instead of color names.
"""

from copy import deepcopy
from server.game_engine import GameEngine, ActionResult
from server.caylus.state import (
    PLAYER_COLORS, RESOURCE_TYPES, NON_GOLD_RESOURCES,
    CASTLE_SECTIONS, CASTLE_COUNT_TRIGGERS,
    SPECIAL_BUILDINGS, SPECIAL_BUILDING_IDS,
    NEUTRAL_BUILDINGS, BASIC_BUILDINGS, WOOD_BUILDINGS, STONE_BUILDINGS, PRESTIGE_BUILDINGS,
    FAVOR_TRACKS, PHASES, ROAD_SIZE, FIXED_POSITIONS,
    create_player, generate_road, create_special_state, create_castle, create_building_stock,
    player_name, has_resources, pay_resources, gain_resources,
    get_worker_cost, count_residential_buildings, player_has_building,
    get_castle_batch_options, find_player_by_idx, get_next_active_player,
    all_players_passed, return_worker, can_afford_with_discount, apply_discounted_cost,
)


class CaylusEngine(GameEngine):
    player_count_range = (2, 5)

    # ── Core Interface ───────────────────────────────────────────────

    def initial_state(self, player_ids, player_names):
        players = []
        for i, (pid, pname) in enumerate(zip(player_ids, player_names)):
            players.append(create_player(i, pid, pname))

        turn_order = list(range(len(players)))

        state = {
            "game": "caylus",
            "player_ids": player_ids,
            "player_count": len(players),
            "players": players,
            "road": generate_road(),
            "special_state": create_special_state(),
            "castle": create_castle(),
            "building_stock": create_building_stock(),
            "bailiff_position": 5,
            "provost_position": 5,
            "turn_order": turn_order,
            "current_phase": 0,  # index into PHASES
            "current_player_idx": turn_order[0],
            "turn": 1,
            "passing_scale": [None] * len(players),
            "game_over": False,
            "favor_columns_available": 2,
            # Pending action trackers
            "pending_activation": None,
            "activation_index": -1,
            "provost_phase": None,
            "pending_provost": None,
            "pending_favors": None,
            "pending_gate": None,
            "pending_castle": None,
            "castle_phase": None,
            "pending_inn": None,
            "pending_owner_bonus": None,
            "delayed_transformations": [],
        }
        return state

    def get_player_view(self, state, player_id):
        # Caylus is open-information, so we return full state with player context
        view = deepcopy(state)
        pidx = self._player_idx(state, player_id)
        view["your_player_id"] = player_id
        view["your_player_idx"] = pidx
        view["valid_actions"] = self.get_valid_actions(state, player_id)
        return view

    def get_valid_actions(self, state, player_id):
        pidx = self._player_idx(state, player_id)
        if pidx is None or state["game_over"]:
            return []

        # Pending favors — the favor picker player acts
        pf = state.get("pending_favors")
        if pf:
            entry = pf["queue"][pf["queue_index"]]
            if entry["player_idx"] != pidx:
                return []
            return self._get_favor_actions(state, pidx, pf)

        # Pending gate
        pg = state.get("pending_gate")
        if pg:
            if pg["player_idx"] != pidx:
                return []
            return self._get_gate_actions(state, pg)

        # Pending owner bonus
        ob = state.get("pending_owner_bonus")
        if ob:
            if ob["owner_idx"] != pidx:
                return []
            return [{"kind": "owner_bonus", "resource": r} for r in ob["options"]]

        # Pending inn
        pi = state.get("pending_inn")
        if pi:
            if pi["player_idx"] != pidx:
                return []
            return [
                {"kind": "inn_choice", "stay": True, "description": "Stay in Inn"},
                {"kind": "inn_choice", "stay": False, "description": "Leave Inn"},
            ]

        # Pending provost move
        pp = state.get("pending_provost")
        if pp:
            if pp["player_idx"] != pidx:
                return []
            return self._get_provost_actions(state, pp)

        # Pending activation
        pa = state.get("pending_activation")
        if pa:
            if pa["worker_idx"] != pidx:
                return []
            return self._get_activation_actions(state, pa)

        # Pending castle
        pc = state.get("pending_castle")
        if pc:
            if pc["player_idx"] != pidx:
                return []
            return self._get_castle_actions(state, pidx)

        phase = state["current_phase"]

        # Phase 0: Income — auto, anyone can trigger
        if phase == 0:
            # Only first player in turn order triggers income
            if pidx == state["turn_order"][0]:
                return [{"kind": "collect_income", "description": "Collect income for all players"}]
            return []

        # Phase 1: Worker placement
        if phase == 1:
            if state["current_player_idx"] != pidx:
                return []
            return self._get_placement_actions(state, pidx)

        return []

    def apply_action(self, state, player_id, action):
        state = deepcopy(state)
        pidx = self._player_idx(state, player_id)
        if pidx is None:
            raise ValueError("Unknown player")

        kind = action.get("kind")
        log = []

        # ── Favor actions ────────────────────────────────────────
        if kind == "favor_choice":
            return self._apply_favor_choice(state, pidx, action)
        if kind == "favor_sub_choice":
            return self._apply_favor_sub_choice(state, pidx, action)

        # ── Gate action ──────────────────────────────────────────
        if kind == "gate_choice":
            return self._apply_gate_choice(state, pidx, action)

        # ── Owner bonus ──────────────────────────────────────────
        if kind == "owner_bonus":
            return self._apply_owner_bonus(state, pidx, action)

        # ── Inn choice ───────────────────────────────────────────
        if kind == "inn_choice":
            return self._apply_inn_choice(state, pidx, action)

        # ── Provost move ─────────────────────────────────────────
        if kind == "move_provost":
            return self._apply_move_provost(state, pidx, action)

        # ── Activation choice ────────────────────────────────────
        if kind == "activation_choice":
            return self._apply_activation_choice(state, pidx, action)

        # ── Castle batch ─────────────────────────────────────────
        if kind == "castle_contribute":
            return self._apply_castle_contribute(state, pidx, action)
        if kind == "castle_skip":
            return self._apply_castle_skip(state, pidx, action)

        # ── Phase 0: Income ──────────────────────────────────────
        if kind == "collect_income":
            return self._apply_collect_income(state, pidx)

        # ── Phase 1: Worker placement ────────────────────────────
        if kind == "place_worker":
            return self._apply_place_worker(state, pidx, action)
        if kind == "place_special":
            return self._apply_place_special(state, pidx, action)
        if kind == "place_castle":
            return self._apply_place_castle(state, pidx)
        if kind == "pass":
            return self._apply_pass(state, pidx)

        raise ValueError(f"Unknown action kind: {kind}")

    def get_waiting_for(self, state):
        if state["game_over"]:
            return []

        # Check pending actions first — they target specific players
        for key in ["pending_favors", "pending_gate", "pending_owner_bonus",
                     "pending_inn", "pending_provost", "pending_activation",
                     "pending_castle"]:
            pending = state.get(key)
            if pending:
                if key == "pending_favors":
                    entry = pending["queue"][pending["queue_index"]]
                    pidx = entry["player_idx"]
                else:
                    pidx = pending.get("player_idx")
                    if pidx is None:
                        pidx = pending.get("owner_idx")
                    if pidx is None:
                        pidx = pending.get("worker_idx")
                if pidx is not None:
                    p = find_player_by_idx(state, pidx)
                    if p:
                        return [p["player_id"]]
                return []

        phase = state["current_phase"]
        if phase == 0:
            p = find_player_by_idx(state, state["turn_order"][0])
            return [p["player_id"]] if p else []
        if phase == 1:
            p = find_player_by_idx(state, state["current_player_idx"])
            return [p["player_id"]] if p else []

        return []

    def get_phase_info(self, state):
        phase_idx = state["current_phase"]
        phase = PHASES[phase_idx] if phase_idx < len(PHASES) else PHASES[-1]

        desc = phase["name"]
        # Add context about what's happening
        if state.get("pending_favors"):
            entry = state["pending_favors"]["queue"][state["pending_favors"]["queue_index"]]
            p = find_player_by_idx(state, entry["player_idx"])
            desc = f"Favor choice — {player_name(p)}" if p else "Favor choice"
        elif state.get("pending_gate"):
            p = find_player_by_idx(state, state["pending_gate"]["player_idx"])
            desc = f"Gate redirect — {player_name(p)}" if p else "Gate redirect"
        elif state.get("pending_provost"):
            p = find_player_by_idx(state, state["pending_provost"]["player_idx"])
            desc = f"Move Provost — {player_name(p)}" if p else "Move Provost"
        elif state.get("pending_activation"):
            pa = state["pending_activation"]
            desc = f"Activate {pa['building_name']}"
        elif state.get("pending_castle"):
            p = find_player_by_idx(state, state["pending_castle"]["player_idx"])
            desc = f"Castle contribution — {player_name(p)}" if p else "Castle contribution"
        elif phase_idx == 1:
            p = find_player_by_idx(state, state["current_player_idx"])
            desc = f"Place Workers — {player_name(p)}" if p else "Place Workers"

        return {
            "phase": phase["id"],
            "phase_name": phase["name"],
            "round": state["turn"],
            "description": desc,
        }

    # ── Private Helpers ──────────────────────────────────────────────

    def _player_idx(self, state, player_id):
        for p in state["players"]:
            if p["player_id"] == player_id:
                return p["index"]
        return None

    def _result(self, state, log=None, game_over=None):
        if game_over is None:
            game_over = state.get("game_over", False)
        return ActionResult(new_state=state, log=log or [], game_over=game_over)

    def _collect_log(self, result_or_log):
        """Normalize internal method returns: extract log from ActionResult or return list as-is."""
        if isinstance(result_or_log, ActionResult):
            return result_or_log.log
        return result_or_log if result_or_log else []

    # ── Phase 0: Income ──────────────────────────────────────────────

    def _apply_collect_income(self, state, pidx):
        if state["current_phase"] != 0:
            raise ValueError("Not income phase")
        log = []
        for p in state["players"]:
            income = 2
            income += count_residential_buildings(state, p["index"])
            if player_has_building(state, p["index"], "p_library"):
                income += 1
            if player_has_building(state, p["index"], "p_hotel"):
                income += 2
            p["deniers"] += income
            log.append(f"{player_name(p)} collects {income}$")

        state["current_phase"] = 1
        state["current_player_idx"] = state["turn_order"][0]
        log.append("— Phase 2: Place Workers —")
        return self._result(state, log)

    # ── Phase 1: Worker Placement ────────────────────────────────────

    def _get_placement_actions(self, state, pidx):
        p = find_player_by_idx(state, pidx)
        if not p or p["passed"]:
            return []

        actions = []
        avail = p["workers_total"] - p["workers_placed"]
        is_inn = p["inn_occupant"]
        cost = 1 if is_inn else get_worker_cost(state)

        if avail > 0 and p["deniers"] >= 1:  # minimum cost is 1 (own building)
            # Road buildings
            for i, slot in enumerate(state["road"]):
                if not slot["building"]:
                    continue
                if slot["building"]["type"] in ("prestige", "residential"):
                    continue
                if slot["worker"] is not None:
                    continue
                is_own = slot["house"] == pidx
                slot_cost = 1 if is_own else cost
                if p["deniers"] >= slot_cost:
                    actions.append({
                        "kind": "place_worker",
                        "road_index": i,
                        "cost": slot_cost,
                        "building_name": slot["building"]["name"],
                        "is_own": is_own,
                        "description": f"Place on {slot['building']['name']} (pos {i+1}) for {slot_cost}$",
                    })

            # Special buildings
            ss = state["special_state"]
            for sid in SPECIAL_BUILDING_IDS:
                if sid == "gate" and ss["gate"]["worker"] is None:
                    if p["deniers"] >= cost:
                        actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                        "description": f"Place on Gate for {cost}$"})
                elif sid == "trading_post" and ss["trading_post"]["worker"] is None:
                    if p["deniers"] >= cost:
                        actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                        "description": f"Place on Trading Post for {cost}$"})
                elif sid == "merchants_guild" and ss["merchants_guild"]["worker"] is None:
                    if p["deniers"] >= cost:
                        actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                        "description": f"Place on Merchants' Guild for {cost}$"})
                elif sid == "joust_field" and ss["joust_field"]["worker"] is None:
                    if p["deniers"] >= cost:
                        actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                        "description": f"Place on Joust Field for {cost}$"})
                elif sid == "stables":
                    if pidx not in ss["stables"] and any(s is None for s in ss["stables"]):
                        if p["deniers"] >= cost:
                            actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                            "description": f"Place on Stables for {cost}$"})
                elif sid == "inn":
                    if ss["inn"]["left"] is None:
                        if p["deniers"] >= cost:
                            actions.append({"kind": "place_special", "special_id": sid, "cost": cost,
                                            "description": f"Place on Inn for {cost}$"})

            # Castle
            if pidx not in state["castle"]["workers"]:
                if p["deniers"] >= cost:
                    actions.append({"kind": "place_castle", "cost": cost,
                                    "description": f"Place in Castle for {cost}$"})

        # Always can pass
        actions.append({"kind": "pass", "description": "Pass"})
        return actions

    def _apply_place_worker(self, state, pidx, action):
        if state["current_phase"] != 1:
            raise ValueError("Not worker phase")
        p = find_player_by_idx(state, pidx)
        if state["current_player_idx"] != pidx or p["passed"]:
            raise ValueError("Not your turn")

        road_index = action.get("road_index")
        if road_index is None or road_index < 0 or road_index >= len(state["road"]):
            raise ValueError("Invalid road index")

        slot = state["road"][road_index]
        if not slot["building"] or slot["building"]["type"] in ("prestige", "residential"):
            raise ValueError("Cannot place on this building")
        if slot["worker"] is not None:
            raise ValueError("Building already occupied")

        avail = p["workers_total"] - p["workers_placed"]
        if avail <= 0:
            raise ValueError("No workers available")

        is_own = slot["house"] == pidx
        cost = 1 if is_own else (1 if p["inn_occupant"] else get_worker_cost(state))
        if p["deniers"] < cost:
            raise ValueError("Not enough deniers")

        p["deniers"] -= cost
        p["workers_placed"] += 1
        slot["worker"] = pidx

        log = []
        if slot["house"] is not None and slot["house"] != pidx:
            owner = find_player_by_idx(state, slot["house"])
            if owner:
                owner["score"] += 1
                log.append(f"{player_name(p)} → {slot['building']['name']} ({player_name(owner)}'s, +1VP) for {cost}$")
        elif is_own:
            log.append(f"{player_name(p)} → own {slot['building']['name']} for {cost}$")
        else:
            log.append(f"{player_name(p)} → {slot['building']['name']} for {cost}$")

        if all_players_passed(state):
            return self._advance_to_phase3(state, log)
        state["current_player_idx"] = get_next_active_player(state, pidx)
        return self._result(state, log)

    def _apply_place_special(self, state, pidx, action):
        if state["current_phase"] != 1:
            raise ValueError("Not worker phase")
        p = find_player_by_idx(state, pidx)
        if state["current_player_idx"] != pidx or p["passed"]:
            raise ValueError("Not your turn")

        special_id = action.get("special_id")
        ss = state["special_state"]
        cost = 1 if p["inn_occupant"] else get_worker_cost(state)

        avail = p["workers_total"] - p["workers_placed"]
        if avail <= 0:
            raise ValueError("No workers available")
        if p["deniers"] < cost:
            raise ValueError("Not enough deniers")

        # Validate and place
        if special_id == "stables":
            if pidx in ss["stables"] or not any(s is None for s in ss["stables"]):
                raise ValueError("Cannot place on Stables")
            idx = ss["stables"].index(None)
            ss["stables"][idx] = pidx
        elif special_id == "inn":
            if ss["inn"]["left"] is not None:
                raise ValueError("Inn left slot occupied")
            ss["inn"]["left"] = pidx
        elif special_id in ("gate", "trading_post", "merchants_guild", "joust_field"):
            if ss[special_id]["worker"] is not None:
                raise ValueError(f"{SPECIAL_BUILDINGS[special_id]['name']} already occupied")
            ss[special_id]["worker"] = pidx
        else:
            raise ValueError(f"Unknown special building: {special_id}")

        p["deniers"] -= cost
        p["workers_placed"] += 1

        log = [f"{player_name(p)} → {SPECIAL_BUILDINGS[special_id]['name']} for {cost}$"]

        if all_players_passed(state):
            return self._advance_to_phase3(state, log)
        state["current_player_idx"] = get_next_active_player(state, pidx)
        return self._result(state, log)

    def _apply_place_castle(self, state, pidx):
        if state["current_phase"] != 1:
            raise ValueError("Not worker phase")
        p = find_player_by_idx(state, pidx)
        if state["current_player_idx"] != pidx or p["passed"]:
            raise ValueError("Not your turn")

        if pidx in state["castle"]["workers"]:
            raise ValueError("Already have worker in castle")

        avail = p["workers_total"] - p["workers_placed"]
        if avail <= 0:
            raise ValueError("No workers available")

        cost = 1 if p["inn_occupant"] else get_worker_cost(state)
        if p["deniers"] < cost:
            raise ValueError("Not enough deniers")

        p["deniers"] -= cost
        p["workers_placed"] += 1
        state["castle"]["workers"].append(pidx)

        log = [f"{player_name(p)} → Castle for {cost}$"]

        if all_players_passed(state):
            return self._advance_to_phase3(state, log)
        state["current_player_idx"] = get_next_active_player(state, pidx)
        return self._result(state, log)

    def _apply_pass(self, state, pidx):
        if state["current_phase"] != 1:
            raise ValueError("Not worker phase")
        p = find_player_by_idx(state, pidx)
        if state["current_player_idx"] != pidx or p["passed"]:
            raise ValueError("Not your turn")

        slot_idx = None
        for i, s in enumerate(state["passing_scale"]):
            if s is None:
                slot_idx = i
                break
        if slot_idx is None:
            slot_idx = len(state["passing_scale"]) - 1

        state["passing_scale"][slot_idx] = pidx
        p["passed"] = True
        p["pass_order"] = slot_idx

        log = []
        if slot_idx == 0:
            p["deniers"] += 1
            log.append(f"{player_name(p)} passes (first — gains 1$)")
        else:
            log.append(f"{player_name(p)} passes")

        if all_players_passed(state):
            return self._advance_to_phase3(state, log)
        state["current_player_idx"] = get_next_active_player(state, pidx)
        return self._result(state, log)

    # ── Phase 3: Special Buildings ───────────────────────────────────

    def _advance_to_phase3(self, state, log):
        state["current_phase"] = 2
        log.append("— Phase 3: Special Buildings —")
        more_log = self._process_special_buildings(state)
        log.extend(more_log)
        return self._result(state, log)

    def _process_special_buildings(self, state):
        """Process special buildings in order. Returns log entries.
        May set pending state and stop (returning partial log)."""
        log = []
        ss = state["special_state"]

        # Gate
        if ss["gate"]["worker"] is not None:
            gate_pidx = ss["gate"]["worker"]
            p = find_player_by_idx(state, gate_pidx)
            road_targets = [i for i, s in enumerate(state["road"])
                            if s["building"] and s["worker"] is None
                            and s["building"]["type"] not in ("residential", "prestige")]
            special_targets = []
            if ss["trading_post"]["worker"] is None:
                special_targets.append("trading_post")
            if ss["merchants_guild"]["worker"] is None:
                special_targets.append("merchants_guild")
            if ss["joust_field"]["worker"] is None:
                special_targets.append("joust_field")
            if any(s is None for s in ss["stables"]) and gate_pidx not in ss["stables"]:
                special_targets.append("stables")
            if ss["inn"]["left"] is None:
                special_targets.append("inn")
            can_castle = gate_pidx not in state["castle"]["workers"]

            if road_targets or special_targets or can_castle:
                log.append(f"{player_name(p)} may redirect Gate worker")
                ss["gate"]["worker"] = None
                state["pending_gate"] = {
                    "player_idx": gate_pidx,
                    "special_targets": special_targets,
                    "can_castle": can_castle,
                }
                return log  # Pause for player choice
            else:
                log.append(f"{player_name(p)}'s Gate — no unoccupied buildings")
                return_worker(state, gate_pidx)
                ss["gate"]["worker"] = None

        return self._continue_after_gate(state, log)

    def _continue_after_gate(self, state, log):
        ss = state["special_state"]

        # Trading Post
        if ss["trading_post"]["worker"] is not None:
            tp_pidx = ss["trading_post"]["worker"]
            p = find_player_by_idx(state, tp_pidx)
            p["deniers"] += 3
            log.append(f"{player_name(p)} gains 3$ (Trading Post)")
            return_worker(state, tp_pidx)
            ss["trading_post"]["worker"] = None

        # Merchants' Guild — interactive
        if ss["merchants_guild"]["worker"] is not None:
            mg_pidx = ss["merchants_guild"]["worker"]
            p = find_player_by_idx(state, mg_pidx)
            log.append(f"{player_name(p)} may move provost via Merchants' Guild")
            return_worker(state, mg_pidx)
            ss["merchants_guild"]["worker"] = None
            state["pending_provost"] = {
                "player_idx": mg_pidx,
                "type": "guild",
                "max_delta": 3,
                "min_pos": 0,
                "max_pos": len(state["road"]) - 1,
            }
            return log  # Pause

        return self._continue_special_buildings(state, log)

    def _continue_special_buildings(self, state, log):
        ss = state["special_state"]

        # Joust Field
        if ss["joust_field"]["worker"] is not None:
            jf_pidx = ss["joust_field"]["worker"]
            p = find_player_by_idx(state, jf_pidx)
            if p["deniers"] >= 1 and p["resources"]["cloth"] >= 1:
                p["deniers"] -= 1
                p["resources"]["cloth"] -= 1
                log.append(f"{player_name(p)} pays 1$+1cloth at Joust Field → 1 favor")
                return_worker(state, jf_pidx)
                ss["joust_field"]["worker"] = None
                self._grant_favors(state, [{"player_idx": jf_pidx, "count": 1}], "continue_special")
                return log  # Pause for favor
            else:
                log.append(f"{player_name(p)} can't pay for Joust Field")
            return_worker(state, jf_pidx)
            ss["joust_field"]["worker"] = None

        return self._continue_special_after_joust(state, log)

    def _continue_special_after_joust(self, state, log):
        ss = state["special_state"]

        # Stables
        if any(s is not None for s in ss["stables"]):
            rank = 0
            order_map = {}
            for pidx in ss["stables"]:
                if pidx is not None:
                    order_map[pidx] = rank
                    rank += 1
                    return_worker(state, pidx)
            for pidx in state["turn_order"]:
                if pidx not in order_map:
                    order_map[pidx] = rank
                    rank += 1
            state["turn_order"] = sorted(order_map.keys(), key=lambda x: order_map[x])
            for p in state["players"]:
                pass  # turn_order list already updated
            names = [player_name(find_player_by_idx(state, i)) for i in state["turn_order"]]
            log.append(f"Stables: new turn order — {', '.join(names)}")
            ss["stables"] = [None, None, None]

        # Inn
        if ss["inn"]["left"] is not None:
            if ss["inn"]["right"] is not None:
                old_pidx = ss["inn"]["right"]
                old_p = find_player_by_idx(state, old_pidx)
                if old_p:
                    old_p["inn_occupant"] = False
                return_worker(state, old_pidx)
                log.append(f"{player_name(old_p)} driven out of Inn")
            ss["inn"]["right"] = ss["inn"]["left"]
            ss["inn"]["left"] = None
            new_p = find_player_by_idx(state, ss["inn"]["right"])
            if new_p:
                new_p["inn_occupant"] = True
            log.append(f"{player_name(new_p)} enters Inn (1$ workers)")
        elif ss["inn"]["right"] is not None:
            # Nobody played inn — occupant chooses stay/leave
            state["pending_inn"] = {"player_idx": ss["inn"]["right"]}
            return log  # Pause

        return self._start_provost_phase(state, log)

    # ── Phase 4: Provost Movement ────────────────────────────────────

    def _start_provost_phase(self, state, log):
        state["current_phase"] = 3
        log.append("— Phase 4: Move Provost —")

        order = [s for s in state["passing_scale"] if s is not None]
        for pidx in state["turn_order"]:
            if pidx not in order:
                order.append(pidx)

        state["provost_phase"] = {"order": order, "index": 0}
        return self._advance_provost_phase(state, log)

    def _advance_provost_phase(self, state, log):
        pp = state["provost_phase"]
        if not pp or pp["index"] >= len(pp["order"]):
            return self._finish_provost_phase(state, log)

        pidx = pp["order"][pp["index"]]
        p = find_player_by_idx(state, pidx)
        max_afford = p["deniers"] if p else 0
        max_delta = min(3, max_afford)

        if max_delta == 0:
            log.append(f"{player_name(p)} has no deniers — passes on provost")
            pp["index"] += 1
            return self._advance_provost_phase(state, log)

        state["pending_provost"] = {
            "player_idx": pidx,
            "type": "phase4",
            "max_delta": max_delta,
            "min_pos": 0,
            "max_pos": len(state["road"]) - 1,
        }
        return log  # Pause

    def _finish_provost_phase(self, state, log):
        state["provost_phase"] = None
        state["pending_provost"] = None
        state["current_phase"] = 4
        log.append("— Phase 5: Activate Buildings —")

        # Remove workers beyond provost
        for i in range(state["provost_position"] + 1, len(state["road"])):
            if state["road"][i]["worker"] is not None:
                wc = state["road"][i]["worker"]
                wp = find_player_by_idx(state, wc)
                log.append(f"{player_name(wp)}'s worker beyond provost (pos {i+1}) — returns unused")
                return_worker(state, wc)
                state["road"][i]["worker"] = None
                self._apply_delayed_transformations(state, i, log)

        state["activation_index"] = -1
        state["pending_activation"] = None
        return self._advance_activation(state, log)

    # ── Provost Actions ──────────────────────────────────────────────

    def _get_provost_actions(self, state, pp):
        actions = [{"kind": "move_provost", "delta": 0, "description": "Pass (don't move provost)"}]
        for d in range(-pp["max_delta"], pp["max_delta"] + 1):
            if d == 0:
                continue
            new_pos = state["provost_position"] + d
            if new_pos < pp["min_pos"] or new_pos > pp["max_pos"]:
                continue
            is_free = pp["type"] == "guild"
            cost = 0 if is_free else abs(d)
            direction = "forward" if d > 0 else "backward"
            cost_str = "(free, Guild)" if is_free else f"(-{cost}$)"
            actions.append({
                "kind": "move_provost", "delta": d,
                "description": f"Move provost {abs(d)} {direction} {cost_str}",
            })
        return actions

    def _apply_move_provost(self, state, pidx, action):
        pp = state.get("pending_provost")
        if not pp or pp["player_idx"] != pidx:
            raise ValueError("Not your provost turn")

        delta = action.get("delta", 0)
        p = find_player_by_idx(state, pidx)
        log = []

        if delta == 0:
            log.append(f"{player_name(p)} passes on provost")
        else:
            new_pos = state["provost_position"] + delta
            clamped = max(pp["min_pos"], min(pp["max_pos"], new_pos))
            actual_delta = clamped - state["provost_position"]
            is_free = pp["type"] == "guild"
            cost = 0 if is_free else abs(actual_delta)

            if abs(actual_delta) > pp["max_delta"]:
                raise ValueError("Move too far")

            if abs(actual_delta) > 0 and (is_free or p["deniers"] >= cost):
                if cost > 0:
                    p["deniers"] -= cost
                state["provost_position"] = clamped
                direction = "forward" if actual_delta > 0 else "backward"
                cost_str = "(free, Guild)" if is_free else f"(-{cost}$)"
                log.append(f"{player_name(p)} moves provost {abs(actual_delta)} {direction} to pos {clamped+1} {cost_str}")
            else:
                log.append(f"{player_name(p)} passes on provost")

        state["pending_provost"] = None

        if pp["type"] == "guild":
            more = self._continue_special_buildings(state, [])
            log.extend(self._collect_log(more))
            return self._result(state, log)

        if state["provost_phase"]:
            state["provost_phase"]["index"] += 1
            more = self._advance_provost_phase(state, [])
            log.extend(self._collect_log(more))
        return self._result(state, log)

    # ── Phase 5: Building Activation ─────────────────────────────────

    def _advance_activation(self, state, log):
        for i in range(state["activation_index"] + 1, min(state["provost_position"] + 1, len(state["road"]))):
            slot = state["road"][i]
            if slot["worker"] is None or not slot["building"]:
                continue

            state["activation_index"] = i
            wc = slot["worker"]
            p = find_player_by_idx(state, wc)
            if not p:
                return_worker(state, wc)
                slot["worker"] = None
                continue

            eff = slot["building"].get("effect")
            if not eff:
                return_worker(state, wc)
                slot["worker"] = None
                continue

            # Auto-resolve simple gain
            if eff["type"] == "gain":
                gain_resources(p, eff["resources"])
                gains = ", ".join(f"{a} {r}" for r, a in eff["resources"].items())
                log.append(f"{player_name(p)} activates {slot['building']['name']}: +{gains}")

                # Owner bonus for stone buildings
                if (slot["building"]["type"] == "stone" and slot["house"] is not None
                        and slot["house"] != wc and slot["building"].get("owner_bonus")):
                    owner = find_player_by_idx(state, slot["house"])
                    if owner:
                        bonus = slot["building"]["owner_bonus"]
                        if len(bonus) == 1:
                            owner["resources"][bonus[0]] += 1
                            log.append(f"  {player_name(owner)} +1 {bonus[0]} (owner bonus)")
                        else:
                            return_worker(state, wc)
                            slot["worker"] = None
                            self._apply_delayed_transformations(state, i, log)
                            state["pending_owner_bonus"] = {
                                "owner_idx": slot["house"],
                                "options": bonus,
                                "building_name": slot["building"]["name"],
                            }
                            return log  # Pause

                return_worker(state, wc)
                slot["worker"] = None
                self._apply_delayed_transformations(state, i, log)
                continue

            # Build pending activation for interactive effects
            pending = self._build_pending_activation(state, i, slot, p)
            if pending:
                state["pending_activation"] = pending
                return log  # Pause

            log.append(f"{player_name(p)} activates {slot['building']['name']} — no valid options, skipped")
            return_worker(state, wc)
            slot["worker"] = None

        # No more workers
        state["activation_index"] = -1
        state["pending_activation"] = None
        state["current_phase"] = 5
        log.append("— Phase 6: Castle —")
        return self._process_castle(state, log)

    def _build_pending_activation(self, state, road_index, slot, player):
        wc = slot["worker"]
        b_name = slot["building"]["name"]
        eff = slot["building"]["effect"]

        base = {"road_index": road_index, "worker_idx": wc, "building_name": b_name}

        if eff["type"] == "choice":
            choices = []
            for i, opt in enumerate(eff["options"]):
                label = " + ".join(f"{a} {r}" for r, a in opt.items())
                choices.append({"id": f"opt_{i}", "label": label})
            return {**base, "effect_type": "choice", "choices": choices, "can_skip": slot["building"]["category"] != "production"}

        if eff["type"] == "sell":
            sellable = [r for r in RESOURCE_TYPES if player["resources"].get(r, 0) > 0]
            choices = [{"id": f"sell_{r}", "label": f"Sell 1 {r} for {eff['price']}$"} for r in sellable]
            return {**base, "effect_type": "sell", "choices": choices, "can_skip": True, "price": eff["price"]}

        if eff["type"] == "buy":
            can_buy = player["deniers"] >= eff["cost_per"]
            choices = [{"id": f"buy_{r}", "label": f"Buy 1 {r} ({eff['cost_per']}$)"} for r in NON_GOLD_RESOURCES] if can_buy else []
            return {**base, "effect_type": "buy", "choices": choices, "can_skip": True,
                    "buy_max": eff["max"], "buy_remaining": eff["max"], "buy_cost_per": eff["cost_per"]}

        if eff["type"] == "build":
            stock = state["building_stock"].get(eff["build_type"], [])
            is_prestige = eff["build_type"] == "prestige"
            valid_target = (any(s["building"] and s["building"]["type"] == "residential" and s["house"] == wc
                               for s in state["road"]) if is_prestige
                           else any(s["building"] is None for s in state["road"]))
            choices = []
            for b in stock:
                can_afford = has_resources(player, b.get("cost", {}))
                choices.append({
                    "id": f"build_{b['id']}", "label": b["name"],
                    "cost": b.get("cost", {}), "vp": b.get("vp", 0),
                    "disabled": not can_afford or not valid_target,
                })
            return {**base, "effect_type": "build", "choices": choices, "can_skip": True,
                    "build_type": eff["build_type"], "needs_target": is_prestige}

        if eff["type"] == "church":
            choices = []
            if player["deniers"] >= 2:
                choices.append({"id": "church_2", "label": "Pay 2$ → +3VP"})
            if player["deniers"] >= 4:
                choices.append({"id": "church_4", "label": "Pay 4$ → +5VP"})
            return {**base, "effect_type": "church", "choices": choices, "can_skip": True}

        if eff["type"] == "tailor":
            choices = []
            if player["resources"]["cloth"] >= 1:
                choices.append({"id": "tailor_1", "label": "Pay 1 cloth → +2VP"})
            if player["resources"]["cloth"] >= 3:
                choices.append({"id": "tailor_3", "label": "Pay 3 cloth → +6VP"})
            return {**base, "effect_type": "tailor", "choices": choices, "can_skip": True}

        if eff["type"] == "bank":
            choices = []
            if player["deniers"] >= 2:
                choices.append({"id": "bank_2", "label": "Pay 2$ → 1 gold"})
            if player["deniers"] >= 5:
                choices.append({"id": "bank_5", "label": "Pay 5$ → 2 gold"})
            return {**base, "effect_type": "bank", "choices": choices, "can_skip": True}

        if eff["type"] == "alchemist":
            non_gold = sum(player["resources"].get(r, 0) for r in NON_GOLD_RESOURCES)
            choices = []
            if non_gold >= 2:
                choices.append({"id": "alch_2", "label": "Pay 2 cubes → 1 gold"})
            if non_gold >= 4:
                choices.append({"id": "alch_4", "label": "Pay 4 cubes → 2 gold"})
            return {**base, "effect_type": "alchemist", "choices": choices, "can_skip": True,
                    "alch_picking": False, "alch_target": 0, "alch_picked": 0}

        if eff["type"] == "lawyer":
            choices = []
            for ri, rs in enumerate(state["road"]):
                if not rs["building"] or rs["building"].get("cannot_be_transformed"):
                    continue
                bt = rs["building"]["type"]
                if bt in ("prestige", "residential", "basic"):
                    continue
                if bt == "neutral" or (rs["house"] == wc and bt in ("wood", "stone")):
                    desc = "Transform neutral" if bt == "neutral" else "Transform your building"
                    choices.append({"id": f"lawyer_{ri}", "label": f"{rs['building']['name']} (pos {ri+1})",
                                    "description": desc, "target_index": ri})
            can_pay = player["deniers"] >= 1 and player["resources"]["cloth"] >= 1
            return {**base, "effect_type": "lawyer", "choices": choices if can_pay else [], "can_skip": True}

        return None

    def _get_activation_actions(self, state, pa):
        actions = []
        if pa.get("can_skip"):
            actions.append({"kind": "activation_choice", "choice_id": "skip", "description": "Skip"})
        for c in pa.get("choices", []):
            if not c.get("disabled"):
                actions.append({"kind": "activation_choice", "choice_id": c["id"],
                                "label": c.get("label", ""), "description": c.get("label", c["id"])})
        return actions

    def _apply_activation_choice(self, state, pidx, action):
        pa = state.get("pending_activation")
        if not pa or pa["worker_idx"] != pidx:
            raise ValueError("Not your activation")

        choice_id = action.get("choice_id")
        slot = state["road"][pa["road_index"]]
        p = find_player_by_idx(state, pidx)
        eff = slot["building"].get("effect", {})
        log = []

        if choice_id == "skip":
            log.append(f"{player_name(p)} skips {pa['building_name']}")
            return_worker(state, pidx)
            slot["worker"] = None
            state["pending_activation"] = None
            more = self._advance_activation(state, [])
            log.extend(self._collect_log(more))
            return self._result(state, log)

        if pa["effect_type"] == "choice":
            opt_idx = int(choice_id.split("_")[1])
            chosen = eff["options"][opt_idx]
            gain_resources(p, chosen)
            gains = ", ".join(f"{a} {r}" for r, a in chosen.items())
            log.append(f"{player_name(p)} activates {pa['building_name']}: +{gains}")
            # Owner bonus check
            if (slot["building"]["type"] == "stone" and slot["house"] is not None
                    and slot["house"] != pidx and slot["building"].get("owner_bonus")):
                owner = find_player_by_idx(state, slot["house"])
                if owner:
                    bonus = slot["building"]["owner_bonus"]
                    if len(bonus) == 1:
                        owner["resources"][bonus[0]] += 1
                        log.append(f"  {player_name(owner)} +1 {bonus[0]} (owner bonus)")
                    else:
                        return_worker(state, pidx)
                        slot["worker"] = None
                        state["pending_activation"] = None
                        state["pending_owner_bonus"] = {
                            "owner_idx": slot["house"],
                            "options": bonus,
                            "building_name": slot["building"]["name"],
                        }
                        return self._result(state, log)

        elif pa["effect_type"] == "sell":
            res = choice_id.split("_")[1]
            p["resources"][res] -= 1
            p["deniers"] += pa["price"]
            log.append(f"{player_name(p)} sells 1 {res} for {pa['price']}$ at {pa['building_name']}")

        elif pa["effect_type"] == "buy":
            res = choice_id.split("_")[1]
            p["deniers"] -= pa["buy_cost_per"]
            p["resources"][res] += 1
            log.append(f"{player_name(p)} buys 1 {res} for {pa['buy_cost_per']}$ at {pa['building_name']}")
            remaining = pa.get("buy_remaining", pa["buy_max"]) - 1
            if remaining > 0 and p["deniers"] >= pa["buy_cost_per"]:
                choices = [{"id": f"buy_{r}", "label": f"Buy 1 {r} ({pa['buy_cost_per']}$)"} for r in NON_GOLD_RESOURCES]
                state["pending_activation"] = {**pa, "buy_remaining": remaining, "choices": choices, "can_skip": True}
                return self._result(state, log)

        elif pa["effect_type"] == "church":
            if choice_id == "church_4":
                p["deniers"] -= 4
                p["score"] += 5
                log.append(f"{player_name(p)} Church: -4$ → +5VP")
            else:
                p["deniers"] -= 2
                p["score"] += 3
                log.append(f"{player_name(p)} Church: -2$ → +3VP")

        elif pa["effect_type"] == "tailor":
            if choice_id == "tailor_3":
                p["resources"]["cloth"] -= 3
                p["score"] += 6
                log.append(f"{player_name(p)} Tailor: -3 cloth → +6VP")
            else:
                p["resources"]["cloth"] -= 1
                p["score"] += 2
                log.append(f"{player_name(p)} Tailor: -1 cloth → +2VP")

        elif pa["effect_type"] == "bank":
            if choice_id == "bank_5":
                p["deniers"] -= 5
                p["resources"]["gold"] += 2
                log.append(f"{player_name(p)} Bank: -5$ → +2 gold")
            else:
                p["deniers"] -= 2
                p["resources"]["gold"] += 1
                log.append(f"{player_name(p)} Bank: -2$ → +1 gold")

        elif pa["effect_type"] == "alchemist":
            if not pa.get("alch_picking"):
                count = 4 if choice_id == "alch_4" else 2
                gold = 2 if count == 4 else 1
                available = [{"id": f"alchcube_{r}", "label": f"Give 1 {r}"}
                             for r in NON_GOLD_RESOURCES if p["resources"].get(r, 0) > 0]
                state["pending_activation"] = {
                    **pa, "alch_picking": True, "alch_target": count,
                    "alch_picked": 0, "alch_gold": gold,
                    "choices": available, "can_skip": False, "effect_type": "alchemist",
                }
                return self._result(state, log)
            # Picking cubes
            res = choice_id.replace("alchcube_", "")
            p["resources"][res] -= 1
            new_picked = pa["alch_picked"] + 1
            log.append(f"{player_name(p)} gives 1 {res} to Alchemist ({new_picked}/{pa['alch_target']})")
            if new_picked >= pa["alch_target"]:
                p["resources"]["gold"] += pa["alch_gold"]
                log.append(f"{player_name(p)} Alchemist: → +{pa['alch_gold']} gold")
            else:
                available = [{"id": f"alchcube_{r}", "label": f"Give 1 {r}"}
                             for r in NON_GOLD_RESOURCES if p["resources"].get(r, 0) > 0]
                if available:
                    state["pending_activation"] = {**pa, "alch_picked": new_picked, "choices": available}
                    return self._result(state, log)
                p["resources"]["gold"] += pa["alch_gold"]
                log.append(f"{player_name(p)} Alchemist: ran out → +{pa['alch_gold']} gold")

        elif pa["effect_type"] == "build":
            if pa.get("needs_target") and not pa.get("chosen_building_id"):
                b_id = choice_id.replace("build_", "")
                stock = state["building_stock"][pa["build_type"]]
                b = next((x for x in stock if x["id"] == b_id), None)
                if not b:
                    return_worker(state, pidx)
                    slot["worker"] = None
                    state["pending_activation"] = None
                    more = self._advance_activation(state, [])
                    log.extend(self._collect_log(more))
                    return self._result(state, log)
                targets = []
                for ri, rs in enumerate(state["road"]):
                    if rs["building"] and rs["building"]["type"] == "residential" and rs["house"] == pidx:
                        targets.append({"id": f"ptarget_{ri}", "label": f"Residential (pos {ri+1})", "target_index": ri})
                state["pending_activation"] = {
                    **pa, "effect_type": "prestige_target", "chosen_building_id": b_id,
                    "choices": targets, "can_skip": True,
                }
                return self._result(state, log)

            b_id = choice_id.replace("build_", "")
            stock = state["building_stock"][pa["build_type"]]
            b_idx = next((i for i, b in enumerate(stock) if b["id"] == b_id), None)
            if b_idx is not None:
                b = stock[b_idx]
                pay_resources(p, b.get("cost", {}))
                empty_slot = next((s for s in state["road"] if s["building"] is None and s["index"] not in FIXED_POSITIONS), None)
                if empty_slot:
                    empty_slot["building"] = stock.pop(b_idx)
                    empty_slot["house"] = pidx
                    p["score"] += b.get("vp", 0)
                    p["houses_placed"] += 1
                    log.append(f"{player_name(p)} builds {b['name']} → +{b.get('vp', 0)}VP")
                    if b.get("favor_on_build"):
                        log.append(f"  {b['name']} grants {b['favor_on_build']} favor(s)")
                        return_worker(state, pidx)
                        slot["worker"] = None
                        self._apply_delayed_transformations(state, pa["road_index"], log)
                        state["pending_activation"] = None
                        self._grant_favors(state, [{"player_idx": pidx, "count": b["favor_on_build"]}], "advance_activation")
                        return self._result(state, log)

        elif pa["effect_type"] == "prestige_target":
            target_choice = next((c for c in pa["choices"] if c["id"] == choice_id), None)
            if target_choice:
                target_idx = target_choice["target_index"]
                stock = state["building_stock"]["prestige"]
                b_idx = next((i for i, b in enumerate(stock) if b["id"] == pa["chosen_building_id"]), None)
                if b_idx is not None:
                    b = stock[b_idx]
                    pay_resources(p, b.get("cost", {}))
                    target = state["road"][target_idx]
                    target["building"] = stock.pop(b_idx)
                    p["score"] += b.get("vp", 0)
                    log.append(f"{player_name(p)} builds {b['name']} (replacing Residential at pos {target_idx+1}) → +{b.get('vp', 0)}VP")
                    if b.get("favor_on_build"):
                        log.append(f"  {b['name']} grants {b['favor_on_build']} favor(s)")
                        return_worker(state, pidx)
                        slot["worker"] = None
                        self._apply_delayed_transformations(state, pa["road_index"], log)
                        state["pending_activation"] = None
                        self._grant_favors(state, [{"player_idx": pidx, "count": b["favor_on_build"]}], "advance_activation")
                        return self._result(state, log)

        elif pa["effect_type"] == "lawyer":
            target_choice = next((c for c in pa["choices"] if c["id"] == choice_id), None)
            if target_choice:
                target_idx = target_choice["target_index"]
                p["deniers"] -= 1
                p["resources"]["cloth"] -= 1
                target = state["road"][target_idx]
                old_building = target["building"]
                old_name = old_building["name"]
                was_neutral = old_building["type"] == "neutral"

                if target["worker"] is not None:
                    state["delayed_transformations"].append({
                        "target_index": target_idx,
                        "lawyer_idx": pidx,
                        "was_neutral": was_neutral,
                        "old_building_type": old_building["type"],
                        "old_building": deepcopy(old_building),
                    })
                    log.append(f"{player_name(p)} pays for {old_name} transformation (delayed — worker present)")
                    p["score"] += 2
                else:
                    if not was_neutral and old_building["type"] in ("wood", "stone"):
                        stock_type = old_building["type"]
                        state["building_stock"][stock_type].append(deepcopy(old_building))
                        log.append(f"  {old_name} returned to {stock_type} building stock")
                    target["building"] = {
                        "id": f"res_{target_idx}", "name": "Residential",
                        "type": "residential", "category": "residential",
                        "description": "+1 denier income",
                    }
                    if was_neutral:
                        target["house"] = pidx
                    p["score"] += 2
                    log.append(f"{player_name(p)} transforms {old_name} → Residential (+2VP)")

        # Done — return worker and advance
        return_worker(state, pidx)
        slot["worker"] = None
        self._apply_delayed_transformations(state, pa["road_index"], log)
        state["pending_activation"] = None
        more = self._advance_activation(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    def _apply_delayed_transformations(self, state, road_index, log=None):
        if log is None:
            log = []
        dt_list = state.get("delayed_transformations", [])
        pending = [dt for dt in dt_list if dt["target_index"] == road_index]
        if not pending:
            return
        state["delayed_transformations"] = [dt for dt in dt_list if dt["target_index"] != road_index]
        for dt in pending:
            target = state["road"][dt["target_index"]]
            old_name = dt["old_building"]["name"]
            if not dt["was_neutral"] and dt["old_building_type"] in ("wood", "stone"):
                state["building_stock"][dt["old_building_type"]].append(deepcopy(dt["old_building"]))
                log.append(f"  {old_name} returned to {dt['old_building_type']} building stock")
            target["building"] = {
                "id": f"res_{dt['target_index']}", "name": "Residential",
                "type": "residential", "category": "residential",
                "description": "+1 denier income",
            }
            if dt["was_neutral"]:
                target["house"] = dt["lawyer_idx"]
            log.append(f"  Delayed: {old_name} → Residential (lawyer by {player_name(find_player_by_idx(state, dt['lawyer_idx']))})")

    # ── Owner Bonus ──────────────────────────────────────────────────

    def _apply_owner_bonus(self, state, pidx, action):
        ob = state.get("pending_owner_bonus")
        if not ob or ob["owner_idx"] != pidx:
            raise ValueError("Not your owner bonus")

        resource = action.get("resource")
        if resource not in ob["options"]:
            raise ValueError("Invalid resource choice")

        p = find_player_by_idx(state, pidx)
        p["resources"][resource] += 1
        log = [f"{player_name(p)} takes +1 {resource} (owner bonus for {ob['building_name']})"]
        state["pending_owner_bonus"] = None

        more = self._advance_activation(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    # ── Gate ─────────────────────────────────────────────────────────

    def _get_gate_actions(self, state, pg):
        actions = []
        for i, s in enumerate(state["road"]):
            if (s["building"] and s["worker"] is None
                    and s["building"]["type"] not in ("residential", "prestige")):
                actions.append({"kind": "gate_choice", "target": i,
                                "description": f"Gate → {s['building']['name']} (pos {i+1})"})
        for sid in pg.get("special_targets", []):
            actions.append({"kind": "gate_choice", "target": f"special_{sid}",
                            "description": f"Gate → {SPECIAL_BUILDINGS[sid]['name']}"})
        if pg.get("can_castle"):
            actions.append({"kind": "gate_choice", "target": "castle",
                            "description": "Gate → Castle"})
        actions.append({"kind": "gate_choice", "target": "skip",
                        "description": "Skip (return worker)"})
        return actions

    def _apply_gate_choice(self, state, pidx, action):
        pg = state.get("pending_gate")
        if not pg or pg["player_idx"] != pidx:
            raise ValueError("Not your gate choice")

        target = action.get("target")
        p = find_player_by_idx(state, pidx)
        log = []

        if target == "skip":
            log.append(f"{player_name(p)} skips Gate — worker returns")
            return_worker(state, pidx)
        elif target == "castle":
            state["castle"]["workers"].append(pidx)
            log.append(f"{player_name(p)} Gate → Castle (free)")
        elif isinstance(target, str) and target.startswith("special_"):
            spec_id = target.replace("special_", "")
            ss = state["special_state"]
            if spec_id == "stables":
                idx = ss["stables"].index(None)
                ss["stables"][idx] = pidx
            elif spec_id == "inn":
                ss["inn"]["left"] = pidx
            else:
                ss[spec_id]["worker"] = pidx
            log.append(f"{player_name(p)} Gate → {SPECIAL_BUILDINGS[spec_id]['name']} (free)")
        else:
            # Road index
            road_index = int(target)
            slot = state["road"][road_index]
            if slot["house"] is not None and slot["house"] != pidx:
                owner = find_player_by_idx(state, slot["house"])
                if owner:
                    owner["score"] += 1
                    log.append(f"{player_name(p)} Gate → {slot['building']['name']} ({player_name(owner)}'s, +1VP) (free)")
            else:
                log.append(f"{player_name(p)} Gate → {slot['building']['name']} (pos {road_index+1}) (free)")
            slot["worker"] = pidx

        state["pending_gate"] = None
        more = self._continue_after_gate(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    # ── Inn ──────────────────────────────────────────────────────────

    def _apply_inn_choice(self, state, pidx, action):
        pi = state.get("pending_inn")
        if not pi or pi["player_idx"] != pidx:
            raise ValueError("Not your inn choice")

        stay = action.get("stay", True)
        p = find_player_by_idx(state, pidx)
        log = []

        if stay:
            log.append(f"{player_name(p)} stays in Inn (1$ workers)")
        else:
            p["inn_occupant"] = False
            return_worker(state, pidx)
            state["special_state"]["inn"]["right"] = None
            log.append(f"{player_name(p)} leaves Inn")

        state["pending_inn"] = None
        more = self._start_provost_phase(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    # ── Phase 6: Castle ──────────────────────────────────────────────

    def _process_castle(self, state, log):
        if not state["castle"]["workers"]:
            state["current_phase"] = 6
            log.append("— Phase 7: End of Turn —")
            return self._process_end_turn(state, log)

        state["castle_phase"] = {"worker_index": 0, "houses_this_turn": {}}
        return self._advance_castle_worker(state, log)

    def _advance_castle_worker(self, state, log):
        cp = state["castle_phase"]
        if not cp or cp["worker_index"] >= len(state["castle"]["workers"]):
            return self._finish_castle_phase(state, log)

        wc = state["castle"]["workers"][cp["worker_index"]]
        p = find_player_by_idx(state, wc)
        if not p:
            cp["worker_index"] += 1
            return self._advance_castle_worker(state, log)

        batch_options = get_castle_batch_options(p, state)
        if batch_options:
            state["pending_castle"] = {"player_idx": wc, "can_give": True}
            return log  # Pause

        # Can't give a batch
        sec = state["castle"]["current_section"]
        parts = state["castle"][sec]
        sec_full = all(x is not None for x in parts)
        next_sec = {"dungeon": "walls", "walls": "towers"}.get(sec)
        next_full = next_sec and all(x is not None for x in state["castle"][next_sec])

        if sec == "towers" and sec_full and (not next_sec or next_full):
            log.append(f"{player_name(p)} — no room left in Towers (no penalty)")
        else:
            p["score"] = max(0, p["score"] - 2)
            log.append(f"{player_name(p)} can't contribute to castle → -2VP")

        return_worker(state, wc)
        cp["worker_index"] += 1
        return self._advance_castle_worker(state, log)

    def _get_castle_actions(self, state, pidx):
        p = find_player_by_idx(state, pidx)
        combos = get_castle_batch_options(p, state)
        actions = []
        for combo in combos:
            actions.append({
                "kind": "castle_contribute",
                "res1": combo[0], "res2": combo[1],
                "description": f"Contribute food + {combo[0]} + {combo[1]}",
            })
        actions.append({"kind": "castle_skip", "description": "Stop / Skip castle"})
        return actions

    def _apply_castle_contribute(self, state, pidx, action):
        pc = state.get("pending_castle")
        if not pc or pc["player_idx"] != pidx:
            raise ValueError("Not your castle turn")

        cp = state["castle_phase"]
        wc = state["castle"]["workers"][cp["worker_index"]]
        p = find_player_by_idx(state, wc)

        res1 = action.get("res1")
        res2 = action.get("res2")
        if not res1 or not res2:
            raise ValueError("Must specify resources")
        if p["resources"]["food"] < 1 or p["resources"][res1] < 1 or p["resources"][res2] < 1:
            raise ValueError("Not enough resources")
        if res1 == res2:
            raise ValueError("Resources must be different types")

        p["resources"]["food"] -= 1
        p["resources"][res1] -= 1
        p["resources"][res2] -= 1

        sec = state["castle"]["current_section"]
        parts = state["castle"][sec]
        empty = next((i for i, x in enumerate(parts) if x is None), -1)
        placed_section = sec

        if empty == -1:
            next_sec = {"dungeon": "walls", "walls": "towers"}.get(sec)
            if next_sec:
                parts = state["castle"][next_sec]
                empty = next((i for i, x in enumerate(parts) if x is None), -1)
                placed_section = next_sec

        log = []
        if empty != -1:
            parts[empty] = pidx
            vp = CASTLE_SECTIONS[placed_section]["vp_per_batch"]
            p["score"] += vp
            p["houses_placed"] += 1
            cp["houses_this_turn"][str(wc)] = cp["houses_this_turn"].get(str(wc), 0) + 1
            log.append(f"{player_name(p)} builds {CASTLE_SECTIONS[placed_section]['name']} (food+{res1}+{res2}) → +{vp}VP")

        more_options = get_castle_batch_options(p, state)
        if more_options:
            state["pending_castle"] = {"player_idx": wc, "can_give": True}
            return self._result(state, log)

        state["pending_castle"] = None
        return_worker(state, wc)
        cp["worker_index"] += 1
        more = self._advance_castle_worker(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    def _apply_castle_skip(self, state, pidx, action):
        pc = state.get("pending_castle")
        if not pc or pc["player_idx"] != pidx:
            raise ValueError("Not your castle turn")

        cp = state["castle_phase"]
        wc = state["castle"]["workers"][cp["worker_index"]]
        p = find_player_by_idx(state, wc)
        log = []

        if not cp["houses_this_turn"].get(str(wc)):
            sec = state["castle"]["current_section"]
            parts = state["castle"][sec]
            sec_full = all(x is not None for x in parts)
            next_sec = {"dungeon": "walls", "walls": "towers"}.get(sec)
            next_full = next_sec and all(x is not None for x in state["castle"][next_sec])
            if sec == "towers" and sec_full and (not next_sec or next_full):
                log.append(f"{player_name(p)} — no room left (no penalty)")
            else:
                p["score"] = max(0, p["score"] - 2)
                log.append(f"{player_name(p)} declines to build castle → -2VP")
        else:
            count = cp["houses_this_turn"][str(wc)]
            log.append(f"{player_name(p)} stops building castle ({count} batch{'es' if count > 1 else ''})")

        state["pending_castle"] = None
        return_worker(state, wc)
        cp["worker_index"] += 1
        more = self._advance_castle_worker(state, [])
        log.extend(self._collect_log(more))
        return self._result(state, log)

    def _finish_castle_phase(self, state, log):
        cp = state["castle_phase"]
        best = None
        best_count = 0
        for pidx_str, count in cp["houses_this_turn"].items():
            pidx_val = int(pidx_str)
            if count > best_count:
                best_count = count
                best = pidx_val
            elif count == best_count and best is not None:
                best_idx = state["castle"]["workers"].index(best) if best in state["castle"]["workers"] else 999
                cur_idx = state["castle"]["workers"].index(pidx_val) if pidx_val in state["castle"]["workers"] else 999
                if cur_idx < best_idx:
                    best = pidx_val

        for wc in state["castle"]["workers"]:
            return_worker(state, wc)
        state["castle"]["workers"] = []
        state["castle_phase"] = None
        state["pending_castle"] = None
        state["current_phase"] = 6

        if best is not None and best_count > 0:
            bp = find_player_by_idx(state, best)
            log.append(f"{player_name(bp)} is best castle builder ({best_count} batch{'es' if best_count > 1 else ''}) → 1 favor")
            self._grant_favors(state, [{"player_idx": best, "count": 1}], "after_castle")
            return log

        log.append("— Phase 7: End of Turn —")
        return self._process_end_turn(state, log)

    # ── Phase 7: End Turn ────────────────────────────────────────────

    def _process_end_turn(self, state, log):
        ahead = state["provost_position"] > state["bailiff_position"]
        mv = 2 if ahead else 1
        state["bailiff_position"] = min(state["bailiff_position"] + mv, len(state["road"]) - 1)
        state["provost_position"] = state["bailiff_position"]
        log.append(f"Bailiff moves {mv} → pos {state['bailiff_position']+1}, Provost resets")

        sec = state["castle"]["current_section"]
        parts = state["castle"][sec]
        full = all(p is not None for p in parts)
        do_count = full
        if not do_count and not state["castle"].get(f"{sec}_counted") and state["bailiff_position"] >= CASTLE_COUNT_TRIGGERS.get(sec, 999):
            do_count = True

        if do_count:
            return self._process_castle_count(state, log)

        return self._finish_end_turn(state, log)

    def _process_castle_count(self, state, log):
        sec = state["castle"]["current_section"]
        parts = state["castle"][sec]
        log.append(f"Counting {CASTLE_SECTIONS[sec]['name']}!")

        favor_queue = []
        for p in state["players"]:
            h = sum(1 for x in parts if x == p["index"])
            favors = 0
            if sec == "dungeon":
                if h == 0:
                    p["score"] = max(0, p["score"] - 2)
                    log.append(f"{player_name(p)}: 0 houses → -2VP")
                elif h >= 2:
                    favors = 1
                    log.append(f"{player_name(p)}: {h} houses → 1 favor")
                else:
                    log.append(f"{player_name(p)}: {h} house")
            elif sec == "walls":
                if h == 0:
                    p["score"] = max(0, p["score"] - 3)
                    log.append(f"{player_name(p)}: 0 houses → -3VP")
                elif h >= 5:
                    favors = 3
                    log.append(f"{player_name(p)}: {h} houses → 3 favors")
                elif h >= 3:
                    favors = 2
                    log.append(f"{player_name(p)}: {h} houses → 2 favors")
                elif h >= 2:
                    favors = 1
                    log.append(f"{player_name(p)}: {h} houses → 1 favor")
                else:
                    log.append(f"{player_name(p)}: {h} house")
            else:  # towers
                if h == 0:
                    p["score"] = max(0, p["score"] - 4)
                    log.append(f"{player_name(p)}: 0 houses → -4VP")
                elif h >= 6:
                    favors = 3
                    log.append(f"{player_name(p)}: {h} houses → 3 favors")
                elif h >= 4:
                    favors = 2
                    log.append(f"{player_name(p)}: {h} houses → 2 favors")
                elif h >= 2:
                    favors = 1
                    log.append(f"{player_name(p)}: {h} houses → 1 favor")
                else:
                    log.append(f"{player_name(p)}: {h} house")
            if favors > 0:
                favor_queue.append({"player_idx": p["index"], "count": favors})

        # Advance section
        if sec == "dungeon":
            state["castle"]["dungeon_counted"] = True
            state["castle"]["current_section"] = "walls"
            state["favor_columns_available"] = 4
            log.append("Walls phase begins. Favor cols 3-4 open.")
        elif sec == "walls":
            state["castle"]["walls_counted"] = True
            state["castle"]["current_section"] = "towers"
            state["favor_columns_available"] = 5
            log.append("Towers phase begins. All favor cols open.")
        else:
            state["castle"]["towers_counted"] = True
            state["game_over"] = True
            log.append("Game Over!")

        if favor_queue:
            self._grant_favors(state, favor_queue, "after_count")
            return log

        return self._finish_end_turn(state, log)

    def _finish_end_turn(self, state, log):
        state["turn"] += 1
        state["current_phase"] = 0
        state["current_player_idx"] = state["turn_order"][0]
        state["passing_scale"] = [None] * state["player_count"]
        for p in state["players"]:
            p["passed"] = False
            p["pass_order"] = -1
        state["pending_activation"] = None
        state["activation_index"] = -1
        state["provost_phase"] = None
        state["pending_provost"] = None
        state["pending_favors"] = None
        state["pending_gate"] = None
        state["pending_castle"] = None
        state["castle_phase"] = None
        state["pending_inn"] = None
        state["pending_owner_bonus"] = None
        state["delayed_transformations"] = []

        if state["game_over"]:
            self._process_end_game(state, log)
        else:
            log.append(f"Turn {state['turn']}")

        return log

    def _process_end_game(self, state, log):
        log.append("FINAL SCORING")
        for p in state["players"]:
            gb = p["resources"]["gold"] * 3
            non_gold = sum(p["resources"].get(r, 0) for r in NON_GOLD_RESOURCES)
            cb = non_gold // 3
            db = p["deniers"] // 4
            p["score"] += gb + cb + db
            log.append(f"{player_name(p)}: +{gb}(gold) +{cb}(cubes) +{db}($) = {p['score']}VP total")
        winner = max(state["players"], key=lambda p: p["score"])
        log.append(f"{player_name(winner)} wins with {winner['score']}VP!")

    # ── Favor System ─────────────────────────────────────────────────

    def _grant_favors(self, state, favor_list, return_action):
        queue = [{"player_idx": f["player_idx"], "remaining": f["count"], "tracks_used": []}
                 for f in favor_list if f["count"] > 0]
        if not queue:
            self._dispatch_favor_return(state, return_action)
            return
        state["pending_favors"] = {
            "queue": queue, "queue_index": 0,
            "sub_choice": None, "return_action": return_action,
        }

    def _dispatch_favor_return(self, state, action):
        state["pending_favors"] = None
        # The caller handles continuation based on the return action
        # This is used in _apply_favor_choice to chain back

    def _get_available_favor_tracks(self, state, player_idx, tracks_used):
        p = find_player_by_idx(state, player_idx)
        if not p:
            return []
        max_col = state["favor_columns_available"]
        tracks = []
        for key, track in FAVOR_TRACKS.items():
            current_level = p["favors"].get(key, 0)
            if key in tracks_used:
                continue
            maxed = current_level >= 5
            next_level = 5 if maxed else current_level + 1
            if not maxed and next_level > max_col:
                continue
            tracks.append({
                "key": key, "name": track["name"],
                "next_level": next_level,
                "current_level": current_level,
                "maxed": maxed,
            })
        return tracks

    def _get_favor_actions(self, state, pidx, pf):
        entry = pf["queue"][pf["queue_index"]]

        # Sub-choice mode
        if pf.get("sub_choice"):
            sc = pf["sub_choice"]
            actions = []
            for opt in sc.get("options", []):
                if not opt.get("disabled"):
                    actions.append({
                        "kind": "favor_sub_choice", "choice_id": opt["id"],
                        "label": opt.get("label", ""), "description": opt.get("label", opt["id"]),
                    })
            if sc.get("can_skip", True) and sc["type"] not in ("res4_take",):
                pass  # Most sub-choices don't have skip
            return actions

        # Track selection
        available = self._get_available_favor_tracks(state, entry["player_idx"], entry["tracks_used"])
        return [{"kind": "favor_choice", "track": t["key"],
                 "description": f"{t['name']} (→ level {t['next_level']}{'*' if t['maxed'] else ''})"}
                for t in available]

    def _apply_favor_choice(self, state, pidx, action):
        pf = state.get("pending_favors")
        if not pf:
            raise ValueError("No pending favors")
        entry = pf["queue"][pf["queue_index"]]
        if entry["player_idx"] != pidx:
            raise ValueError("Not your favor turn")

        track_key = action.get("track")
        p = find_player_by_idx(state, pidx)
        log = []

        current_level = p["favors"].get(track_key, 0)
        maxed = current_level >= 5
        next_level = 5 if maxed else current_level + 1
        if not maxed:
            p["favors"][track_key] = next_level
        entry["tracks_used"].append(track_key)

        track = FAVOR_TRACKS[track_key]
        if maxed:
            log.append(f"{player_name(p)} uses {track['name']} favor (maxed at col 5)")
        else:
            log.append(f"{player_name(p)} takes {track['name']} favor → col {next_level}")

        # Handle track-specific effects
        if track_key == "prestige":
            if next_level == 1:
                p["score"] += 1
                log.append("  +1 VP")
            else:
                options = [{"id": f"prestlvl_{lvl}", "label": f"+{lvl} VP"} for lvl in range(1, next_level + 1)]
                pf["sub_choice"] = {"type": "prestige_level_pick", "options": options}
                return self._result(state, log)

        elif track_key == "deniers":
            if next_level == 1:
                p["deniers"] += 3
                log.append("  +3$")
            else:
                options = [{"id": f"denlvl_{lvl}", "label": f"+{lvl + 2}$"} for lvl in range(1, next_level + 1)]
                pf["sub_choice"] = {"type": "deniers_level_pick", "options": options}
                return self._result(state, log)

        elif track_key == "resources":
            if next_level == 1:
                p["resources"]["food"] += 1
                log.append("  +1 food")
            else:
                options = [{"id": "reslvl_1", "label": "+1 food"}]
                if next_level >= 2:
                    options.append({"id": "reslvl_2", "label": "+1 wood/stone"})
                if next_level >= 3:
                    options.append({"id": "reslvl_3", "label": "+1 cloth"})
                if next_level >= 4:
                    options.append({"id": "reslvl_4", "label": "Swap 1→2"})
                if next_level >= 5:
                    options.append({"id": "reslvl_5", "label": "+1 gold"})
                pf["sub_choice"] = {"type": "res_level_pick", "options": options}
                return self._result(state, log)

        elif track_key == "buildings":
            if next_level == 1:
                log.append("  No effect")
            else:
                options = self._get_building_favor_options(state, p, pidx, next_level)
                options.append({"id": "bldlvl_skip", "label": "Skip"})
                if len(options) > 1:
                    pf["sub_choice"] = {"type": "bld_level_pick", "options": options}
                    return self._result(state, log)
                log.append("  No building effects available")

        entry["remaining"] -= 1
        return self._advance_favor_queue(state, log)

    def _get_building_favor_options(self, state, player, pidx, next_level):
        options = []
        has_empty = any(s["building"] is None for s in state["road"])
        if next_level >= 2:
            w_stock = state["building_stock"].get("wood", [])
            options.append({"id": "bldlvl_2", "label": "Carpenter -1",
                            "disabled": not w_stock or not has_empty})
        if next_level >= 3:
            s_stock = state["building_stock"].get("stone", [])
            options.append({"id": "bldlvl_3", "label": "Mason -1",
                            "disabled": not s_stock or not has_empty})
        if next_level >= 4:
            has_target = any(
                rs["building"] and not rs["building"].get("cannot_be_transformed")
                and rs["building"]["type"] not in ("prestige", "residential", "basic")
                and (rs["building"]["type"] == "neutral" or (rs["house"] == pidx and rs["building"]["type"] in ("wood", "stone")))
                for rs in state["road"]
            )
            options.append({"id": "bldlvl_4", "label": "Lawyer",
                            "disabled": not has_target or player["resources"]["cloth"] < 1})
        if next_level >= 5:
            p_stock = state["building_stock"].get("prestige", [])
            has_residential = any(s["building"] and s["building"]["type"] == "residential" and s["house"] == pidx
                                  for s in state["road"])
            options.append({"id": "bldlvl_5", "label": "Architect -1",
                            "disabled": not p_stock or not has_residential})
        return options

    def _apply_favor_sub_choice(self, state, pidx, action):
        pf = state.get("pending_favors")
        if not pf or not pf.get("sub_choice"):
            raise ValueError("No pending sub choice")
        entry = pf["queue"][pf["queue_index"]]
        if entry["player_idx"] != pidx:
            raise ValueError("Not your favor turn")

        choice_id = action.get("choice_id")
        p = find_player_by_idx(state, pidx)
        sc = pf["sub_choice"]
        log = []

        if sc["type"] == "prestige_level_pick":
            lvl = int(choice_id.replace("prestlvl_", ""))
            p["score"] += lvl
            log.append(f"  {player_name(p)} takes +{lvl} VP")
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "deniers_level_pick":
            lvl = int(choice_id.replace("denlvl_", ""))
            amount = lvl + 2
            p["deniers"] += amount
            log.append(f"  {player_name(p)} takes +{amount}$")
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "res_level_pick":
            lvl = int(choice_id.replace("reslvl_", ""))
            if lvl == 1:
                p["resources"]["food"] += 1
                log.append(f"  {player_name(p)} takes +1 food")
            elif lvl == 2:
                pf["sub_choice"] = {"type": "res2", "options": [
                    {"id": "wood", "label": "+1 wood"},
                    {"id": "stone", "label": "+1 stone"},
                ]}
                return self._result(state, log)
            elif lvl == 3:
                p["resources"]["cloth"] += 1
                log.append(f"  {player_name(p)} takes +1 cloth")
            elif lvl == 4:
                give_options = [{"id": r, "label": f"-1 {r}"} for r in RESOURCE_TYPES if p["resources"].get(r, 0) > 0]
                if give_options:
                    pf["sub_choice"] = {"type": "res4_give", "options": give_options}
                    return self._result(state, log)
                log.append(f"  {player_name(p)} has no cubes to trade")
            elif lvl == 5:
                p["resources"]["gold"] += 1
                log.append(f"  {player_name(p)} takes +1 gold")
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "res2":
            p["resources"][choice_id] += 1
            log.append(f"  {player_name(p)} picks +1 {choice_id}")
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "res4_give":
            p["resources"][choice_id] -= 1
            log.append(f"  {player_name(p)} gives 1 {choice_id}")
            pf["sub_choice"] = {"type": "res4_take", "picks": 0, "max_picks": 2, "options": [
                {"id": r, "label": f"+1 {r}"} for r in NON_GOLD_RESOURCES
            ]}
            return self._result(state, log)

        if sc["type"] == "res4_take":
            p["resources"][choice_id] += 1
            sc["picks"] += 1
            log.append(f"  {player_name(p)} takes +1 {choice_id} ({sc['picks']}/2)")
            if sc["picks"] >= sc["max_picks"]:
                pf["sub_choice"] = None
                entry["remaining"] -= 1
                return self._advance_favor_queue(state, log)
            return self._result(state, log)

        if sc["type"] == "bld_level_pick":
            if choice_id == "bldlvl_skip":
                log.append(f"  {player_name(p)} skips building effect")
                pf["sub_choice"] = None
                entry["remaining"] -= 1
                return self._advance_favor_queue(state, log)

            lvl = int(choice_id.replace("bldlvl_", ""))
            if lvl in (2, 3, 5):
                build_type = {2: "wood", 3: "stone", 5: "prestige"}[lvl]
                stock = state["building_stock"].get(build_type, [])
                is_prestige = lvl == 5
                options = []
                for b in stock:
                    can_afford, _ = can_afford_with_discount(p, b.get("cost", {}))
                    options.append({"id": f"fbuild_{b['id']}", "label": b["name"], "disabled": not can_afford})
                pf["sub_choice"] = {"type": "build_favor", "build_type": build_type,
                                    "options": options, "discount": 1, "is_prestige": is_prestige}
                return self._result(state, log)
            elif lvl == 4:
                options = []
                for ri, rs in enumerate(state["road"]):
                    if not rs["building"] or rs["building"].get("cannot_be_transformed"):
                        continue
                    bt = rs["building"]["type"]
                    if bt in ("prestige", "residential", "basic"):
                        continue
                    if bt == "neutral" or (rs["house"] == pidx and bt in ("wood", "stone")):
                        options.append({"id": f"flawyer_{ri}", "label": f"{rs['building']['name']} (pos {ri+1})",
                                        "target_index": ri})
                if options:
                    pf["sub_choice"] = {"type": "lawyer_favor", "options": options}
                    return self._result(state, log)
                log.append("  No buildings to transform")

            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "build_favor":
            if choice_id == "skip":
                log.append(f"  {player_name(p)} skips building favor")
            elif sc.get("is_prestige") and not sc.get("chosen_building_id"):
                b_id = choice_id.replace("fbuild_", "")
                targets = []
                for ri, rs in enumerate(state["road"]):
                    if rs["building"] and rs["building"]["type"] == "residential" and rs["house"] == pidx:
                        targets.append({"id": f"fptarget_{ri}", "label": f"Residential (pos {ri+1})", "target_index": ri})
                pf["sub_choice"] = {"type": "build_favor_prestige_target",
                                    "build_type": sc["build_type"], "chosen_building_id": b_id,
                                    "options": targets, "discount": 1}
                return self._result(state, log)
            else:
                b_id = choice_id.replace("fbuild_", "")
                stock = state["building_stock"][sc["build_type"]]
                b_idx = next((i for i, b in enumerate(stock) if b["id"] == b_id), None)
                if b_idx is not None:
                    b = stock[b_idx]
                    apply_discounted_cost(p, b.get("cost", {}))
                    empty_slot = next((s for s in state["road"] if s["building"] is None and s["index"] not in FIXED_POSITIONS), None)
                    if empty_slot:
                        empty_slot["building"] = stock.pop(b_idx)
                        empty_slot["house"] = pidx
                        p["score"] += b.get("vp", 0)
                        p["houses_placed"] += 1
                        log.append(f"  {player_name(p)} builds {b['name']} (favor discount) → +{b.get('vp', 0)}VP")
                        if b.get("favor_on_build"):
                            log.append(f"  {b['name']} grants {b['favor_on_build']} favor(s)")
                            entry["remaining"] += b["favor_on_build"]

            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "build_favor_prestige_target":
            if choice_id == "skip":
                log.append(f"  {player_name(p)} skips prestige placement")
            else:
                opt = next((o for o in sc["options"] if o["id"] == choice_id), None)
                if opt:
                    stock = state["building_stock"]["prestige"]
                    b_idx = next((i for i, b in enumerate(stock) if b["id"] == sc["chosen_building_id"]), None)
                    if b_idx is not None:
                        b = stock[b_idx]
                        apply_discounted_cost(p, b.get("cost", {}))
                        target = state["road"][opt["target_index"]]
                        target["building"] = stock.pop(b_idx)
                        p["score"] += b.get("vp", 0)
                        log.append(f"  {player_name(p)} builds {b['name']} (favor discount) → +{b.get('vp', 0)}VP")
                        if b.get("favor_on_build"):
                            log.append(f"  {b['name']} grants {b['favor_on_build']} favor(s)")
                            entry["remaining"] += b["favor_on_build"]
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        if sc["type"] == "lawyer_favor":
            if choice_id == "skip":
                log.append(f"  {player_name(p)} skips lawyer favor")
            else:
                opt = next((o for o in sc["options"] if o["id"] == choice_id), None)
                if opt and p["resources"]["cloth"] >= 1:
                    p["resources"]["cloth"] -= 1
                    target = state["road"][opt["target_index"]]
                    old_building = target["building"]
                    old_name = old_building["name"]
                    was_neutral = old_building["type"] == "neutral"
                    if not was_neutral and old_building["type"] in ("wood", "stone"):
                        state["building_stock"][old_building["type"]].append(deepcopy(old_building))
                    target["building"] = {
                        "id": f"res_{opt['target_index']}", "name": "Residential",
                        "type": "residential", "category": "residential",
                        "description": "+1 denier income",
                    }
                    if was_neutral:
                        target["house"] = pidx
                    p["score"] += 2
                    log.append(f"  {player_name(p)} transforms {old_name} → Residential (+2VP, -1 cloth) (favor lawyer)")
            pf["sub_choice"] = None
            entry["remaining"] -= 1
            return self._advance_favor_queue(state, log)

        return self._result(state, log)

    def _advance_favor_queue(self, state, log):
        pf = state["pending_favors"]
        if not pf:
            return self._result(state, log)

        entry = pf["queue"][pf["queue_index"]]
        if entry["remaining"] > 0:
            avail = self._get_available_favor_tracks(state, entry["player_idx"], entry["tracks_used"])
            if not avail:
                p = find_player_by_idx(state, entry["player_idx"])
                log.append(f"{player_name(p)} has no more available favor tracks")
                entry["remaining"] = 0
            else:
                return self._result(state, log)

        pf["queue_index"] += 1
        if pf["queue_index"] < len(pf["queue"]):
            return self._result(state, log)

        # All done — dispatch return
        return_action = pf["return_action"]
        state["pending_favors"] = None

        if return_action == "continue_special":
            more = self._continue_special_after_joust(state, [])
            log.extend(self._collect_log(more))
        elif return_action == "advance_activation":
            more = self._advance_activation(state, [])
            log.extend(self._collect_log(more))
        elif return_action == "after_castle":
            log.append("— Phase 7: End of Turn —")
            more = self._process_end_turn(state, [])
            log.extend(self._collect_log(more))
        elif return_action == "after_count":
            more = self._finish_end_turn(state, [])
            log.extend(self._collect_log(more))

        return self._result(state, log)
