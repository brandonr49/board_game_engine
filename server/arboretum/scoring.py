"""
Arboretum scoring logic.

Path-finding algorithm, scoring rights determination, and final score computation.
"""

from server.arboretum.state import parse_key, pos_key, get_neighbors


# ── Path Finding ─────────────────────────────────────────────────────

def find_best_path_for_species(grid, species):
    """
    Find the highest-scoring path through a player's grid for a given species.

    A valid path:
    - Starts and ends with a card of the target species
    - Has length >= 2 cards
    - Each step is orthogonally adjacent
    - Values are strictly ascending along the path
    - Interior cards can be any species

    Returns (score, path) where path is list of (row, col) tuples.
    Returns (0, []) if no valid path exists.
    """
    # Find all positions with the target species (potential start/end points)
    species_positions = []
    for key, card in grid.items():
        if card["species"] == species:
            species_positions.append(parse_key(key))

    if len(species_positions) < 2:
        return 0, []

    result = [0, []]  # [best_score, best_path]

    # DFS from each card of the target species
    for start_pos in species_positions:
        start_card = grid[pos_key(*start_pos)]
        _dfs_paths(grid, species, start_pos, start_card["value"],
                   [start_pos], result)

    return result[0], result[1]


def _dfs_paths(grid, target_species, current_pos, current_value, path, result):
    """DFS to explore all ascending paths from current position."""
    # Check if current position ends on the target species and path >= 2
    if len(path) >= 2:
        end_card = grid[pos_key(*current_pos)]
        if end_card["species"] == target_species:
            score = score_path(path, grid, target_species)
            if score > result[0]:
                result[0] = score
                result[1] = list(path)

    # Max path length is 8 (values 1-8)
    if len(path) >= 8:
        return

    # Explore neighbors
    for nr, nc in get_neighbors(*current_pos):
        nkey = pos_key(nr, nc)
        if nkey not in grid:
            continue
        if (nr, nc) in path:
            continue
        neighbor_card = grid[nkey]
        if neighbor_card["value"] <= current_value:
            continue
        # Valid next step
        path.append((nr, nc))
        _dfs_paths(grid, target_species, (nr, nc), neighbor_card["value"],
                   path, result)
        path.pop()


def score_path(path, grid, target_species):
    """
    Score a valid path.

    - 1 point per card in the path
    - +1 per card if path >= 4 cards AND all cards are the same species
    - +1 if path starts with value 1
    - +2 if path ends with value 8
    """
    length = len(path)
    score = length

    # Check if all cards in path are the target species
    all_same_species = all(
        grid[pos_key(r, c)]["species"] == target_species
        for r, c in path
    )
    if length >= 4 and all_same_species:
        score += length  # double the base

    # Bonus for starting with 1
    start_card = grid[pos_key(*path[0])]
    if start_card["value"] == 1:
        score += 1

    # Bonus for ending with 8
    end_card = grid[pos_key(*path[-1])]
    if end_card["value"] == 8:
        score += 2

    return score


# ── Scoring Rights ───────────────────────────────────────────────────

def determine_scoring_rights(players, active_species):
    """
    For each species, determine which players have the right to score it.

    Rules:
    - Sum the values of cards of that species in each player's hand
    - 1-cancels-8 rule: if a player holds the 1 of a species, the 8 of that
      species in ALL other players' hands is worth 0
    - Highest adjusted sum wins scoring rights
    - Ties: all tied players score
    - All zeros: everyone scores

    Returns dict mapping species_id -> list of player indices who can score.
    Also returns detailed breakdown for UI.
    """
    species_ids = [s["id"] for s in active_species]
    rights = {}
    breakdown = {}

    for species_id in species_ids:
        # Calculate raw hand values per player
        hand_cards = []
        raw_sums = []
        for pi, player in enumerate(players):
            cards_of_species = [c for c in player["hand"] if c["species"] == species_id]
            hand_cards.append(cards_of_species)
            raw_sums.append(sum(c["value"] for c in cards_of_species))

        # Determine who holds the 1
        one_holders = []
        for pi, cards in enumerate(hand_cards):
            if any(c["value"] == 1 for c in cards):
                one_holders.append(pi)

        # Apply 1-cancels-8 rule
        adjusted_sums = list(raw_sums)
        eights_cancelled = {}
        for pi, cards in enumerate(hand_cards):
            has_eight = any(c["value"] == 8 for c in cards)
            if has_eight:
                # Check if any OTHER player holds the 1
                cancelled_by = [oh for oh in one_holders if oh != pi]
                if cancelled_by:
                    adjusted_sums[pi] -= 8
                    eights_cancelled[pi] = cancelled_by

        # Determine who has the right to score
        max_sum = max(adjusted_sums)
        if max_sum == 0:
            # Everyone scores
            eligible = list(range(len(players)))
        else:
            eligible = [pi for pi, s in enumerate(adjusted_sums) if s == max_sum]

        rights[species_id] = eligible
        breakdown[species_id] = {
            "hand_cards": hand_cards,
            "raw_sums": raw_sums,
            "adjusted_sums": adjusted_sums,
            "one_holders": one_holders,
            "eights_cancelled": eights_cancelled,
            "eligible": eligible,
        }

    return rights, breakdown


# ── Final Scoring ────────────────────────────────────────────────────

def compute_final_scores(state):
    """
    Compute final scores for all players.

    Returns detailed scoring results for the UI.
    """
    players = state["players"]
    active_species = state["active_species"]

    rights, rights_breakdown = determine_scoring_rights(players, active_species)

    # Find best paths per species per player
    player_scores = []
    species_results = []

    for species_info in active_species:
        species_id = species_info["id"]
        species_result = {
            "species": species_info,
            "rights": rights_breakdown[species_id],
            "paths": [],
        }

        for pi, player in enumerate(players):
            score, path = find_best_path_for_species(player["grid"], species_id)
            # Only count score if player has scoring rights
            if pi in rights[species_id]:
                actual_score = score
            else:
                actual_score = 0

            species_result["paths"].append({
                "player_index": pi,
                "has_rights": pi in rights[species_id],
                "path": path,
                "path_score": score,
                "actual_score": actual_score,
            })

        species_results.append(species_result)

    # Compute totals
    totals = [0] * len(players)
    for sr in species_results:
        for path_info in sr["paths"]:
            totals[path_info["player_index"]] += path_info["actual_score"]

    # Determine winner
    max_score = max(totals)
    winners = [pi for pi, t in enumerate(totals) if t == max_score]

    return {
        "species_results": species_results,
        "totals": totals,
        "winners": winners,
    }
