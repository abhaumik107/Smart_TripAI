"""
Correctness tests for the nearest-neighbor route builder and the
underlying Haversine-based distance matrix.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms.route_builder import build_route
from api.places import Attraction
from utils.helpers import haversine_distance_km


def make_attraction(name, lat, lon):
    return Attraction(
        place_id=name,
        name=name,
        latitude=lat,
        longitude=lon,
        rating=4.0,
        review_count=100,
        category="museum",
        address="",
        visit_duration_minutes=60,
        personalized_score=0.5,
    )


def test_nearest_neighbor_picks_closest_first():
    start = (0.0, 0.0)
    # B is closer to start than A or C.
    a = make_attraction("A", 0.05, 0.05)
    b = make_attraction("B", 0.01, 0.01)
    c = make_attraction("C", 0.08, 0.08)

    result = build_route(start, [a, b, c])
    ordered_names = [stop.attraction.name for stop in result.stops]

    assert ordered_names[0] == "B"
    assert len(result.stops) == 3
    assert result.total_travel_minutes > 0


def test_empty_attractions_returns_empty_route():
    result = build_route((0.0, 0.0), [])
    assert result.stops == []
    assert result.total_travel_minutes == 0.0


def test_haversine_known_distance():
    # Approx distance between Mumbai and Pune is ~120 km.
    mumbai = (19.0760, 72.8777)
    pune = (18.5204, 73.8567)
    distance = haversine_distance_km(mumbai, pune)
    assert 100 < distance < 140


if __name__ == "__main__":
    test_nearest_neighbor_picks_closest_first()
    test_empty_attractions_returns_empty_route()
    test_haversine_known_distance()
    print("All route builder tests passed.")
