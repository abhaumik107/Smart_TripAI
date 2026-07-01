# multi_day_knapsack.py - assigns attractions across multiple days to maximize total score
# extends single-day knapsack: each attraction goes to exactly one day or gets skipped
# uses memoized recursion over (item_index, remaining_caps_per_day) - cheaper than dense table

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Tuple

from api.places import Attraction
from utils.helpers import get_logger, round_up_to_block
import config

logger = get_logger(__name__)


@dataclass
class DayPlan:
    # attractions assigned to one day, before routing
    day_index: int  # 0-based
    attractions: List[Attraction] = field(default_factory=list)
    total_score: float = 0.0
    total_visit_minutes: int = 0
    capacity_minutes: int = 0


@dataclass
class MultiDayKnapsackResult:
    # one DayPlan per day + trip-level totals
    day_plans: List[DayPlan]
    total_score: float
    total_visit_minutes: int


def solve_multi_day_knapsack(
    attractions: List[Attraction],
    available_visit_minutes_per_day: List[float],
    time_block_minutes: int = config.TIME_BLOCK_MINUTES,
) -> MultiDayKnapsackResult:
    # jointly assigns attractions to days - not a greedy per-day loop, which would starve later days
    num_days = len(available_visit_minutes_per_day)
    if num_days == 0:
        return MultiDayKnapsackResult([], 0.0, 0)

    if not attractions:
        logger.warning("solve_multi_day_knapsack called with an empty attraction list.")
        empty_plans = [
            DayPlan(day_index=d, capacity_minutes=int(available_visit_minutes_per_day[d]))
            for d in range(num_days)
        ]
        return MultiDayKnapsackResult(empty_plans, 0.0, 0)

    # round up durations to blocks, same as single-day knapsack
    weights_blocks: List[int] = [
        max(1, round_up_to_block(a.visit_duration_minutes, time_block_minutes) // time_block_minutes)
        for a in attractions
    ]
    capacity_blocks_per_day: Tuple[int, ...] = tuple(
        max(0, int(minutes // time_block_minutes))
        for minutes in available_visit_minutes_per_day
    )

    n = len(attractions)
    values = [a.personalized_score for a in attractions]

    @lru_cache(maxsize=None)
    def best_score(i: int, caps: Tuple[int, ...]) -> float:
        # returns best total score achievable from attraction i onward given remaining caps
        if i == n:
            return 0.0
        best = best_score(i + 1, caps)  # skip attraction i
        w = weights_blocks[i]
        for d in range(num_days):
            if caps[d] >= w:  # try placing in day d if it fits
                new_caps = caps[:d] + (caps[d] - w,) + caps[d + 1:]
                candidate = values[i] + best_score(i + 1, new_caps)
                if candidate > best:
                    best = candidate
        return best

    optimal_total = best_score(0, capacity_blocks_per_day)

    # backtrack through memo table to recover day assignments
    assignment: List[int] = [-1] * n  # -1 means excluded
    caps = capacity_blocks_per_day
    assigned_items: set = set()  # track which indices are already assigned
    for i in range(n):
        if i in assigned_items:
            continue
        current_best = best_score(i, caps)
        if abs(current_best - best_score(i + 1, caps)) < 1e-9:
            continue  # skipping i still hits optimal, so it's excluded
        w = weights_blocks[i]
        placed = False
        for d in range(num_days):
            if caps[d] >= w:
                new_caps = caps[:d] + (caps[d] - w,) + caps[d + 1:]
                candidate = values[i] + best_score(i + 1, new_caps)
                if abs(candidate - current_best) < 1e-9:
                    assignment[i] = d
                    caps = new_caps
                    assigned_items.add(i)
                    placed = True
                    break
        if not placed:
            # couldn't place this item — exclude it to avoid phantom duplicates
            assignment[i] = -1

    best_score.cache_clear()  # drop memo table after each call

    # build per-day plan objects from the assignment list
    day_plans = [
        DayPlan(day_index=d, capacity_minutes=int(available_visit_minutes_per_day[d]))
        for d in range(num_days)
    ]
    for i, day_idx in enumerate(assignment):
        if day_idx == -1:
            continue
        plan = day_plans[day_idx]
        plan.attractions.append(attractions[i])
        plan.total_score = round(plan.total_score + attractions[i].personalized_score, 4)
        plan.total_visit_minutes += attractions[i].visit_duration_minutes

    total_score = round(sum(p.total_score for p in day_plans), 4)
    total_visit_minutes = sum(p.total_visit_minutes for p in day_plans)

    logger.info(
        "Multi-day knapsack: %d days | %d/%d attractions assigned | total_score=%.3f | total_visit=%dmin",
        num_days, sum(len(p.attractions) for p in day_plans), n, total_score, total_visit_minutes,
    )

    return MultiDayKnapsackResult(
        day_plans=day_plans,
        total_score=total_score,
        total_visit_minutes=total_visit_minutes,
    )