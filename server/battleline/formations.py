"""
Formation evaluation and flag-claim proof for Battle Line.

Formation ranks (highest to lowest):
  5 – Wedge:          same color, consecutive values
  4 – Phalanx:        all same value
  3 – Battalion Order: same color
  2 – Skirmish Line:  consecutive values
  1 – Host:           anything else

Comparison: (rank, sum) — higher rank wins; ties broken by higher sum,
then by who completed first (completion_turn).
"""

from itertools import combinations, product

from server.battleline.state import TROOP_COLORS, get_available_troops

# ── Formation Constants ───────────────────────────────────────────────

WEDGE = 5
PHALANX = 4
BATTALION = 3
SKIRMISH = 2
HOST = 1


# ── Core Formation Evaluation ────────────────────────────────────────

def _is_consecutive(values):
    """Check if sorted values form a consecutive sequence."""
    s = sorted(values)
    return all(s[i] + 1 == s[i + 1] for i in range(len(s) - 1))


def _classify_formation(colors, values):
    """
    Given concrete lists of colors and values (no wilds),
    return (rank, sum).
    """
    assert len(colors) == len(values)
    total = sum(values)
    same_color = len(set(colors)) == 1
    same_value = len(set(values)) == 1
    consecutive = _is_consecutive(values)

    if same_color and consecutive:
        return (WEDGE, total)
    if same_value:
        return (PHALANX, total)
    if same_color:
        return (BATTALION, total)
    if consecutive:
        return (SKIRMISH, total)
    return (HOST, total)


# ── Wildcard Expansion ────────────────────────────────────────────────

def _wild_options(card):
    """
    Return list of (color, value) options for a morale-tactic wildcard.
    Leaders (alexander/darius): any color × values 1-10
    Companion Cavalry: any color × value 8
    Shield Bearers: any color × values 1-3
    """
    card_id = card.get("id", "")
    colors = list(TROOP_COLORS)

    if card_id in ("alexander", "darius"):
        return [(c, v) for c in colors for v in range(1, 11)]
    elif card_id == "companion_cavalry":
        return [(c, 8) for c in colors]
    elif card_id == "shield_bearers":
        return [(c, v) for c in colors for v in range(1, 4)]
    else:
        # Not a wild card — shouldn't happen
        return []


def best_formation(cards, has_fog=False):
    """
    Evaluate the best possible formation for a set of cards,
    considering morale-tactic wildcards.

    If has_fog is True, formation rank is ignored (HOST) — maximize sum.

    Returns (rank, sum).
    """
    if not cards:
        return (HOST, 0)

    # Separate fixed troops from wilds
    fixed_colors = []
    fixed_values = []
    wilds = []

    for card in cards:
        if card["type"] == "troop":
            fixed_colors.append(card["color"])
            fixed_values.append(card["value"])
        else:
            # Morale tactic acting as wild
            wilds.append(card)

    if not wilds:
        # No wildcards — straightforward evaluation
        rank, total = _classify_formation(fixed_colors, fixed_values)
        if has_fog:
            return (HOST, total)
        return (rank, total)

    # Enumerate wildcard assignments
    wild_option_lists = [_wild_options(w) for w in wilds]
    best = (HOST, 0)

    for assignment in product(*wild_option_lists):
        colors = list(fixed_colors)
        values = list(fixed_values)
        for c, v in assignment:
            colors.append(c)
            values.append(v)
        rank, total = _classify_formation(colors, values)
        if has_fog:
            rank = HOST
        candidate = (rank, total)
        if candidate > best:
            best = candidate

    return best


# ── Flag Claim Proof ──────────────────────────────────────────────────

def can_claim_flag(state, claimer, flag_idx):
    """
    Determine if `claimer` (player index 0 or 1) can claim flag `flag_idx`.

    Rules:
    1. Claimer must have a complete formation (required card count).
    2. Compute claimer's best formation.
    3. If opponent also complete: direct comparison. Ties decided by
       completion_turn (who completed first wins).
    4. If opponent incomplete: enumerate all possible completions from
       publicly-available troop cards. If NO completion can strictly beat
       claimer, claim succeeds. (Ties favor claimer since they would have
       completed first.)
    """
    flag = state["flags"][flag_idx]

    if flag["claimed_by"] is not None:
        return False

    opponent = 1 - claimer
    has_fog = "fog" in flag["environment"]
    has_mud = "mud" in flag["environment"]
    required = 4 if has_mud else 3

    claimer_cards = flag["slots"][claimer]
    opponent_cards = flag["slots"][opponent]

    # Claimer must have filled their side
    if len(claimer_cards) < required:
        return False

    claimer_formation = best_formation(claimer_cards, has_fog=has_fog)

    # If opponent is also complete, direct comparison
    if len(opponent_cards) >= required:
        opponent_formation = best_formation(opponent_cards, has_fog=has_fog)
        if claimer_formation > opponent_formation:
            return True
        if claimer_formation == opponent_formation:
            # Tie: whoever completed first wins
            ct = flag["completion_turn"]
            return ct[claimer] is not None and (ct[opponent] is None or ct[claimer] <= ct[opponent])
        return False

    # Opponent incomplete — proof by exhaustion
    available = get_available_troops(state)
    available_list = sorted(available)  # deterministic order
    needed = required - len(opponent_cards)

    # Fixed cards already on opponent's side
    opp_fixed = list(opponent_cards)

    for combo in combinations(available_list, needed):
        # Build hypothetical opponent cards
        hypothetical = list(opp_fixed) + [{"type": "troop", "color": c, "value": v} for c, v in combo]
        opp_formation = best_formation(hypothetical, has_fog=has_fog)
        if opp_formation > claimer_formation:
            # Opponent COULD beat claimer — can't claim
            return False
        # Equal formations: claimer completed first, so tie favors claimer

    # No possible completion beats claimer
    return True
