"""
Correctness tests for the manual 0/1 Knapsack DP implementation, including
a hand-verifiable classic case and an edge case for zero capacity.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.knapsack import solve_knapsack
from api.places import Attraction


def make_attraction(name, score, duration_minutes):
    return Attraction(
        place_id=name,
        name=name,
        latitude=0.0,
        longitude=0.0,
        rating=4.0,
        review_count=100,
        category="museum",
        address="",
        visit_duration_minutes=duration_minutes,
        personalized_score=score,
    )


def test_classic_knapsack_case():
    # Classic textbook case (weights=[1,3,4,5], values=[1,4,5,7], cap=7)
    # scaled to minutes using a 1-minute block size for exact comparison.
    # Optimal known answer: items with weights 3+4=7 -> value 4+5=9.
    items = [
        make_attraction("A", 1, 1),
        make_attraction("B", 4, 3),
        make_attraction("C", 5, 4),
        make_attraction("D", 7, 5),
    ]
    result = solve_knapsack(items, available_visit_minutes=7, time_block_minutes=1)
    assert result.total_score == 9.0
    assert result.total_visit_minutes == 7
    selected_names = {a.name for a in result.selected_attractions}
    assert selected_names == {"B", "C"}


def test_zero_capacity_returns_empty():
    items = [make_attraction("A", 5, 60)]
    result = solve_knapsack(items, available_visit_minutes=0, time_block_minutes=15)
    assert result.selected_attractions == []
    assert result.total_score == 0.0


def test_single_item_fits():
    items = [make_attraction("A", 0.8, 60)]
    result = solve_knapsack(items, available_visit_minutes=90, time_block_minutes=15)
    assert len(result.selected_attractions) == 1
    assert result.selected_attractions[0].name == "A"


def test_item_too_large_is_excluded():
    items = [make_attraction("A", 0.9, 300)]
    result = solve_knapsack(items, available_visit_minutes=60, time_block_minutes=15)
    assert result.selected_attractions == []


if __name__ == "__main__":
    test_classic_knapsack_case()
    test_zero_capacity_returns_empty()
    test_single_item_fits()
    test_item_too_large_is_excluded()
    print("All knapsack tests passed.")
