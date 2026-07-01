# Using 0/1 knapsack DP to pick attractions that maximize score within time budget

from dataclasses import dataclass
from typing import List

from api.places import Attraction
from utils.helpers import get_logger, round_up_to_block
import config

logger = get_logger(__name__)


@dataclass
class KnapsackResult:
    # what the optimizer picked and some stats about it
    selected_attractions: List[Attraction]
    total_score: float
    total_visit_minutes: int
    capacity_minutes: int


def solve_knapsack(
    attractions: List[Attraction],
    available_visit_minutes: float,
    time_block_minutes: int = config.TIME_BLOCK_MINUTES,
) -> KnapsackResult:
    # weight = visit duration, value = personalized_score, capacity = available time
    if not attractions:
        logger.warning("solve_knapsack called with an empty attraction list.")
        return KnapsackResult([], 0.0, 0, 0)

    # round durations up to nearest block so we never under-count time needed
    weights_blocks = [
        max(1, round_up_to_block(a.visit_duration_minutes, time_block_minutes) // time_block_minutes)
        for a in attractions
    ]
    capacity_blocks = int(available_visit_minutes // time_block_minutes)

    n = len(attractions)

    if capacity_blocks <= 0:
        logger.info("Available visiting time too small for any attraction.")
        return KnapsackResult([], 0.0, 0, capacity_blocks * time_block_minutes)

    # dp[i][c] = best score using first i attractions with c blocks of capacity
    dp = [[0.0] * (capacity_blocks + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        item_weight = weights_blocks[i - 1]
        item_value = attractions[i - 1].personalized_score
        for c in range(capacity_blocks + 1):
            best_without = dp[i - 1][c]
            best_with = (
                dp[i - 1][c - item_weight] + item_value
                if item_weight <= c
                else -1.0  # doesn't fit
            )
            dp[i][c] = max(best_without, best_with)

    # backtrack through dp table to recover which items were selected
    selected_indices: List[int] = []
    remaining_capacity = capacity_blocks
    for i in range(n, 0, -1):
        if dp[i][remaining_capacity] != dp[i - 1][remaining_capacity]:
            selected_indices.append(i - 1)
            remaining_capacity -= weights_blocks[i - 1]

    selected_indices.reverse()
    selected = [attractions[i] for i in selected_indices]
    total_score = round(sum(a.personalized_score for a in selected), 4)
    total_visit_minutes = sum(a.visit_duration_minutes for a in selected)

    logger.info(
        "Knapsack selected %d/%d attractions | total_score=%.3f | visit_time=%dmin / capacity=%dmin",
        len(selected), n, total_score, total_visit_minutes, capacity_blocks * time_block_minutes,
    )

    return KnapsackResult(
        selected_attractions=selected,
        total_score=total_score,
        total_visit_minutes=total_visit_minutes,
        capacity_minutes=capacity_blocks * time_block_minutes,
    )
