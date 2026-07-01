# optimizer.py - full itinerary pipeline: score → knapsack → cap → gap-fill → route → trim

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import config
from algorithms.knapsack import solve_knapsack
from algorithms.multi_day_knapsack import solve_multi_day_knapsack
from algorithms.route_builder import RouteStop, RouteResult, build_route, build_distance_matrix
from api.places import Attraction
from ml.scorer import BaseScorer, WeightedScorer
from services.preprocessing import preprocess, filter_by_min_score
from utils.helpers import get_logger

logger = get_logger(__name__)

# max stops per category per day — prevents any single category dominating a day
PER_DAY_CATEGORY_CAP: Dict[str, int] = {
    "restaurant": 2, "cafe": 1, "bakery": 1, "bar": 2, "night_club": 1,
    "store": 1, "shopping_mall": 2, "market": 1, "movie_theater": 1, "amusement_park": 2,
    "museum": 4, "park": 2, "place_of_worship": 3,
}
_DEFAULT_PER_DAY_CAP = 4


@dataclass
class ItineraryResult:
    stops: List[RouteStop]
    total_score: float
    total_visit_minutes: int
    total_travel_minutes: float
    available_minutes: float
    utilization_percent: float


@dataclass
class DayItineraryResult:
    day_index: int
    stops: List[RouteStop]
    total_score: float
    total_visit_minutes: int
    total_travel_minutes: float
    available_minutes: float
    utilization_percent: float


@dataclass
class MultiDayItineraryResult:
    days: List[DayItineraryResult]
    total_score: float
    total_visit_minutes: int
    total_travel_minutes: float


def _apply_per_day_category_cap(
    attractions: List[Attraction],
) -> Tuple[List[Attraction], List[Attraction]]:
    # returns (kept, dropped) — dropped go back to caller for gap-fill
    sorted_attractions = sorted(attractions, key=lambda a: a.personalized_score, reverse=True)
    category_counts: Dict[str, int] = {}
    kept, dropped = [], []
    for attraction in sorted_attractions:
        cap = PER_DAY_CATEGORY_CAP.get(attraction.category, _DEFAULT_PER_DAY_CAP)
        count = category_counts.get(attraction.category, 0)
        if count < cap:
            kept.append(attraction)
            category_counts[attraction.category] = count + 1
        else:
            dropped.append(attraction)
    if dropped:
        logger.info("Per-day cap dropped %d stops: %s", len(dropped), [a.name for a in dropped])
    return kept, dropped


def _gap_fill(
    selected: List[Attraction],
    all_attractions: List[Attraction],
    visit_budget_minutes: float,
) -> List[Attraction]:
    # after cap trimming, try to fill leftover time with next-best unselected attractions
    # sorts candidates by score-per-minute so we maximise both score and utilization
    selected_ids = {a.place_id for a in selected}
    used_minutes = sum(a.visit_duration_minutes for a in selected)
    category_counts: Dict[str, int] = {}
    for a in selected:
        category_counts[a.category] = category_counts.get(a.category, 0) + 1

    candidates = sorted(
        [a for a in all_attractions if a.place_id not in selected_ids],
        key=lambda a: a.personalized_score / max(a.visit_duration_minutes, 1),
        reverse=True,
    )

    added = []
    for candidate in candidates:
        cap = PER_DAY_CATEGORY_CAP.get(candidate.category, _DEFAULT_PER_DAY_CAP)
        if category_counts.get(candidate.category, 0) >= cap:
            continue  # would violate daily category cap
        if used_minutes + candidate.visit_duration_minutes <= visit_budget_minutes:
            selected.append(candidate)
            selected_ids.add(candidate.place_id)
            used_minutes += candidate.visit_duration_minutes
            category_counts[candidate.category] = category_counts.get(candidate.category, 0) + 1
            added.append(candidate.name)

    if added:
        logger.info("Gap-fill added %d stops: %s", len(added), added)
    return selected


class TripOptimizer:

    def __init__(self, scorer: BaseScorer = None) -> None:
        self.scorer: BaseScorer = scorer or WeightedScorer()

    def generate_itinerary(
        self,
        start_location: Tuple[float, float],
        candidate_attractions: List[Attraction],
        user_interests: Set[str],
        available_hours: float,
    ) -> ItineraryResult:
        available_minutes = available_hours * 60.0
        travel_buffer_minutes = available_minutes * config.TRAVEL_TIME_BUFFER_RATIO
        visit_budget_minutes = available_minutes - travel_buffer_minutes

        attractions = preprocess(candidate_attractions)
        attractions = self.scorer.score_attractions(attractions, user_interests)
        attractions = filter_by_min_score(attractions)

        knapsack_result = solve_knapsack(attractions, visit_budget_minutes)
        selected = knapsack_result.selected_attractions

        selected, _ = _apply_per_day_category_cap(selected)
        selected = _gap_fill(selected, attractions, visit_budget_minutes)

        matrix = build_distance_matrix(start_location, attractions)
        route_result = build_route(start_location, selected, precomputed_matrix=matrix)

        # trim if total time still exceeds budget after gap-fill
        while selected and (
            sum(a.visit_duration_minutes for a in selected) + route_result.total_travel_minutes
            > available_minutes
        ):
            dropped = self._drop_weakest_attraction(selected)
            selected = [a for a in selected if a.place_id != dropped.place_id]
            route_result = build_route(start_location, selected, precomputed_matrix=matrix)

        total_visit_minutes = sum(a.visit_duration_minutes for a in selected)
        total_score = round(sum(a.personalized_score for a in selected), 4)
        total_used_minutes = total_visit_minutes + route_result.total_travel_minutes
        utilization_percent = (
            round((total_used_minutes / available_minutes) * 100, 1)
            if available_minutes > 0 else 0.0
        )

        logger.info(
            "Final itinerary: %d stops | score=%.3f | visit=%dmin | travel=%.1fmin | utilization=%.1f%%",
            len(selected), total_score, total_visit_minutes,
            route_result.total_travel_minutes, utilization_percent,
        )

        return ItineraryResult(
            stops=route_result.stops,
            total_score=total_score,
            total_visit_minutes=total_visit_minutes,
            total_travel_minutes=route_result.total_travel_minutes,
            available_minutes=available_minutes,
            utilization_percent=utilization_percent,
        )

    def generate_multi_day_itinerary(
        self,
        start_location: Tuple[float, float],
        candidate_attractions: List[Attraction],
        user_interests: Set[str],
        available_hours_per_day: float,
        num_days: int,
    ) -> MultiDayItineraryResult:
        available_minutes_per_day = available_hours_per_day * 60.0
        travel_buffer_minutes = available_minutes_per_day * config.TRAVEL_TIME_BUFFER_RATIO
        visit_budget_minutes = available_minutes_per_day - travel_buffer_minutes

        attractions = preprocess(candidate_attractions)
        attractions = self.scorer.score_attractions(attractions, user_interests)
        attractions = filter_by_min_score(attractions)
        # sort descending so multi-day knapsack sees best attractions first
        # this ensures top-scored tourist places land in Day 1, not scattered randomly
        attractions = sorted(attractions, key=lambda a: a.personalized_score, reverse=True)

        global_matrix = build_distance_matrix(start_location, attractions)

        per_day_budgets = [visit_budget_minutes] * num_days
        knapsack_result = solve_multi_day_knapsack(attractions, per_day_budgets)

        # seed globally_assigned_ids with EVERY attraction the knapsack assigned to any day
        # this is the critical fix: without this, attractions dropped by the per-day category cap
        # are not in the set and gap-fill can reassign them to a different day → cross-day repeat
        globally_assigned_ids: Set[str] = {
            a.place_id
            for day_plan in knapsack_result.day_plans
            for a in day_plan.attractions
        }

        day_results: List[DayItineraryResult] = []
        for day_plan in knapsack_result.day_plans:
            selected = day_plan.attractions
            selected, cap_dropped = _apply_per_day_category_cap(selected)

            # gap-fill only from attractions the knapsack never assigned to any day
            available_for_fill = [
                a for a in attractions if a.place_id not in globally_assigned_ids
            ]
            selected = _gap_fill(selected, available_for_fill, visit_budget_minutes)
            # mark gap-filled additions as used so they can't appear in later days
            globally_assigned_ids.update(a.place_id for a in selected)

            route_result = build_route(start_location, selected, precomputed_matrix=global_matrix)

            # trim if over budget after gap-fill
            while selected and (
                sum(a.visit_duration_minutes for a in selected) + route_result.total_travel_minutes
                > available_minutes_per_day
            ):
                dropped = self._drop_weakest_attraction(selected)
                selected = [a for a in selected if a.place_id != dropped.place_id]
                route_result = build_route(start_location, selected, precomputed_matrix=global_matrix)
                logger.info("Day %d: trim dropped '%s'", day_plan.day_index + 1, dropped.name)

            total_visit_minutes = sum(a.visit_duration_minutes for a in selected)
            total_score = round(sum(a.personalized_score for a in selected), 4)
            total_used_minutes = total_visit_minutes + route_result.total_travel_minutes
            utilization_percent = (
                round((total_used_minutes / available_minutes_per_day) * 100, 1)
                if available_minutes_per_day > 0 else 0.0
            )

            day_results.append(
                DayItineraryResult(
                    day_index=day_plan.day_index,
                    stops=route_result.stops,
                    total_score=total_score,
                    total_visit_minutes=total_visit_minutes,
                    total_travel_minutes=route_result.total_travel_minutes,
                    available_minutes=available_minutes_per_day,
                    utilization_percent=utilization_percent,
                )
            )

        trip_total_score = round(sum(d.total_score for d in day_results), 4)
        trip_total_visit_minutes = sum(d.total_visit_minutes for d in day_results)
        trip_total_travel_minutes = round(sum(d.total_travel_minutes for d in day_results), 1)

        logger.info(
            "Multi-day itinerary: %d days | score=%.3f | visit=%dmin | travel=%.1fmin",
            num_days, trip_total_score, trip_total_visit_minutes, trip_total_travel_minutes,
        )

        return MultiDayItineraryResult(
            days=day_results,
            total_score=trip_total_score,
            total_visit_minutes=trip_total_visit_minutes,
            total_travel_minutes=trip_total_travel_minutes,
        )

    @staticmethod
    def _drop_weakest_attraction(attractions: List[Attraction]) -> Attraction:
        # drop worst score-per-minute ratio — maximises both score and time efficiency
        return min(
            attractions,
            key=lambda a: a.personalized_score / max(a.visit_duration_minutes, 1),
        )
