# route_builder.py - sequences selected attractions using nearest-neighbor heuristic
# TSP is NP-hard so we use greedy NN instead of exact solver - good enough for small n

from dataclasses import dataclass
from typing import Dict, List, Tuple

from api.places import Attraction
from utils.helpers import get_logger, haversine_distance_km, km_to_minutes

logger = get_logger(__name__)


@dataclass
class RouteStop:
    # one stop in the final ordered itinerary
    attraction: Attraction
    arrival_order: int
    travel_minutes_from_previous: float


@dataclass
class RouteResult:
    # ordered stops + total travel time for the day
    stops: List[RouteStop]
    total_travel_minutes: float


def build_distance_matrix(
    start_location: Tuple[float, float], attractions: List[Attraction]
) -> Dict[int, Dict[int, float]]:
    # travel-time matrix (minutes) between start (-1) and all attractions
    # haversine_distance_km is lru_cache'd so repeated calls between same pairs are free
    points: Dict[int, Tuple[float, float]] = {-1: start_location}
    for idx, attraction in enumerate(attractions):
        points[idx] = (attraction.latitude, attraction.longitude)

    matrix: Dict[int, Dict[int, float]] = {}
    node_ids = list(points.keys())
    for a in node_ids:
        matrix[a] = {}
        for b in node_ids:
            if a == b:
                matrix[a][b] = 0.0
                continue
            # pass tuples so lru_cache can hash them
            distance_km = haversine_distance_km(points[a], points[b])
            matrix[a][b] = km_to_minutes(distance_km)

    return matrix


def build_route(
    start_location: Tuple[float, float],
    attractions: List[Attraction],
    precomputed_matrix: Dict[int, Dict[int, float]] = None,
) -> RouteResult:
    # greedily picks the nearest unvisited attraction at each step
    # accepts a precomputed matrix to avoid rebuilding when re-routing after drops
    if not attractions:
        return RouteResult(stops=[], total_travel_minutes=0.0)

    distance_matrix = precomputed_matrix or build_distance_matrix(start_location, attractions)

    unvisited = set(range(len(attractions)))
    current_node = -1  # -1 = starting location
    stops: List[RouteStop] = []
    total_travel_minutes = 0.0
    order = 1

    while unvisited:
        nearest_idx = min(unvisited, key=lambda idx: distance_matrix[current_node][idx])
        travel_minutes = distance_matrix[current_node][nearest_idx]

        stops.append(
            RouteStop(
                attraction=attractions[nearest_idx],
                arrival_order=order,
                travel_minutes_from_previous=round(travel_minutes, 1),
            )
        )

        total_travel_minutes += travel_minutes
        current_node = nearest_idx
        unvisited.remove(nearest_idx)
        order += 1

    logger.info(
        "Route built for %d stops | total_travel_time=%.1f min",
        len(stops), total_travel_minutes,
    )

    return RouteResult(stops=stops, total_travel_minutes=round(total_travel_minutes, 1))