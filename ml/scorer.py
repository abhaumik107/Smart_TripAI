# scorer.py - personalized attraction scoring with pool-relative normalization

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Set
import math

import config
from api.places import Attraction
from utils.helpers import get_logger

logger = get_logger(__name__)


class BaseScorer(ABC):

    @abstractmethod
    def score(self, attraction: Attraction, user_interests: Set[str]) -> float:
        raise NotImplementedError

    def score_attractions(
        self, attractions: Iterable[Attraction], user_interests: Set[str]
    ) -> List[Attraction]:
        scored = []
        for attraction in attractions:
            attraction.personalized_score = self.score(attraction, user_interests)
            scored.append(attraction)
        return scored


class WeightedScorer(BaseScorer):

    def __init__(self, weights: config.ScoringWeights = config.SCORING_WEIGHTS) -> None:
        weights.validate()
        self.weights = weights

    def score_attractions(
        self, attractions: Iterable[Attraction], user_interests: Set[str]
    ) -> List[Attraction]:
        # compute pool-relative normalization bounds before scoring
        # this means scores reflect quality *within this candidate set*, not absolute ceilings
        pool = list(attractions)
        if not pool:
            return pool

        ratings = [a.rating for a in pool if a.rating > 0]
        counts = [a.review_count for a in pool if a.review_count > 0]

        self._max_rating = max(ratings) if ratings else 5.0
        self._min_rating = min(ratings) if ratings else 0.0
        self._max_log_count = math.log1p(max(counts)) if counts else math.log1p(10_000)

        scored = []
        for attraction in pool:
            attraction.personalized_score = self.score(attraction, user_interests)
            scored.append(attraction)

        logger.info(
            "Scored %d attractions | rating range [%.1f, %.1f] | top score %.4f",
            len(scored),
            self._min_rating,
            self._max_rating,
            max(a.personalized_score for a in scored),
        )
        return scored

    # tourist/landmark categories get a prestige boost so they outcompete food in the knapsack
    _CATEGORY_PRESTIGE: Dict[str, float] = {
        "museum": 1.20, "historical_landmark": 1.20, "tourist_attraction": 1.20,
        "monument": 1.15, "art_gallery": 1.15, "place_of_worship": 1.10,
        "zoo": 1.10, "botanical_garden": 1.10, "park": 1.05,
        "natural_feature": 1.05, "amusement_park": 1.05,
        "restaurant": 0.85, "cafe": 0.80, "bakery": 0.75,
        "bar": 0.80, "night_club": 0.85, "store": 0.75, "market": 0.90,
    }

    def score(self, attraction: Attraction, user_interests: Set[str]) -> float:
        normalized_rating = self._normalize_rating(attraction.rating)
        normalized_popularity = self._normalize_popularity(attraction.review_count)
        interest_match = self._interest_match(attraction.category, user_interests)

        rating_contribution = self.weights.rating_weight * normalized_rating
        popularity_contribution = self.weights.popularity_weight * normalized_popularity
        interest_contribution = self.weights.interest_weight * interest_match

        base_score = rating_contribution + popularity_contribution + interest_contribution
        # apply category prestige multiplier — tourist spots score higher, food spots lower
        prestige = self._CATEGORY_PRESTIGE.get(attraction.category, 1.0)
        final_score = round(min(max(base_score * prestige, 0.0), 1.0), 4)

        # store the real weighted breakdown so the UI can explain *why* this
        # attraction scored the way it did, instead of relying on a separate
        # display-only heuristic that doesn't reflect the actual scorer.
        attraction.score_components = {
            "normalized_rating": round(normalized_rating, 4),
            "normalized_popularity": round(normalized_popularity, 4),
            "interest_match": round(interest_match, 4),
            "rating_contribution": round(rating_contribution, 4),
            "popularity_contribution": round(popularity_contribution, 4),
            "interest_contribution": round(interest_contribution, 4),
            "prestige_multiplier": prestige,
        }

        return final_score

    def _normalize_rating(self, rating: float) -> float:
        # pool-relative: best attraction in this batch scores 1.0
        rating = min(max(rating, 0.0), self._max_rating)
        span = self._max_rating - self._min_rating
        if span < 1e-6:
            return 1.0
        return (rating - self._min_rating) / span

    def _normalize_popularity(self, review_count: int) -> float:
        # log-scale dampens viral outliers; normalized against pool max
        if review_count <= 0:
            return 0.0
        return min(math.log1p(review_count) / self._max_log_count, 1.0)

    @staticmethod
    def _interest_match(category: str, user_interests: Set[str]) -> float:
        # count how many of the user's interests map to this category
        # partial match scores proportionally instead of hard 1.0/0.15 binary
        if not user_interests:
            return 0.15
        matching = sum(
            1 for interest in user_interests
            if category in config.INTEREST_CATEGORY_MAP.get(interest, [])
        )
        if matching == 0:
            return 0.15  # small baseline so non-matching places aren't zeroed out
        return min(0.5 + 0.5 * (matching / len(user_interests)), 1.0)
