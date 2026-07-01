"""
Every tunable constant in the system lives here so that algorithm modules,
services, and the UI never hardcode magic numbers. This makes the system
easy to reason about and easy to tune without touching business logic.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List
from dotenv import load_dotenv
load_dotenv()
# API Configuration

GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")

# If no API key is configured, the app runs in MOCK_MODE
MOCK_MODE: bool = GOOGLE_PLACES_API_KEY.strip() == ""

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_NEARBY_SEARCH_URL = (
    "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
)

PLACES_SEARCH_RADIUS_METERS: int = 35000
PLACES_MAX_RESULTS: int = 100  # needs to be high — heavy filtering downstream reduces pool significantly
# Interests

INTEREST_CATEGORY_MAP: Dict[str, List[str]] = {
    "History": ["museum", "historical_landmark", "place_of_worship", "monument"],
    "Museums": ["museum", "art_gallery"],
    "Nature": ["park", "natural_feature", "zoo", "botanical_garden"],
    "Food": ["restaurant", "cafe", "bakery"],
    "Shopping": ["shopping_mall", "store", "market"],
    "Nightlife": ["bar", "night_club"],
    "Entertainment": ["amusement_park", "tourist_attraction"],
    "Spiritual": ["place_of_worship", "cemetery", "hindu_temple", "mosque", "church"],
    "Beaches & Outdoors": ["natural_feature", "park", "campground", "rv_park"],
    "Sports & Recreation": ["stadium", "sports_complex", "bowling_alley", "golf_course"],
}

ALL_INTERESTS: List[str] = list(INTEREST_CATEGORY_MAP.keys())

# Scoring weights (Recommendation Engine)

@dataclass(frozen=True)
class ScoringWeights:
    """Weights for the weighted personalized-score formula.

    final_score = rating_weight * normalized_rating
                + popularity_weight * normalized_popularity
                + interest_weight * interest_match
    """

    rating_weight: float = 0.40
    popularity_weight: float = 0.20
    interest_weight: float = 0.40

    def validate(self) -> None:
        total = self.rating_weight + self.popularity_weight + self.interest_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")

SCORING_WEIGHTS = ScoringWeights()
SCORING_WEIGHTS.validate()

# Knapsack / Itinerary Optimization Configuration

# The DP table is built over discretized time blocks (minutes). 15-minute
# blocks give a good balance between DP table size and scheduling precision.
TIME_BLOCK_MINUTES: int = 15

# The Knapsack DP optimizes the visiting time budget (available_time - travel_buffer)
TRAVEL_TIME_BUFFER_RATIO: float = 0.25
DEFAULT_VISIT_DURATION_MINUTES: int = 60

DEFAULT_VISIT_DURATIONS: Dict[str, int] = {
    "museum": 90,
    "art_gallery": 60,
    "historical_landmark": 45,
    "monument": 30,
    "place_of_worship": 30,
    "park": 60,
    "natural_feature": 45,
    "zoo": 120,
    "botanical_garden": 60,
    "restaurant": 55,
    "cafe": 40,
    "bakery": 20,
    "shopping_mall": 90,
    "store": 30,
    "market": 45,
    "bar": 60,
    "night_club": 90,
    "amusement_park": 150,
    "movie_theater": 120,
    "tourist_attraction": 60,
    "stadium": 120,
    "sports_complex": 90,
    "bowling_alley": 60,
    "golf_course": 120,
    "campground": 60,
    "hindu_temple": 40,
    "mosque": 30,
    "church": 30,
    "cemetery": 30,
}

AVERAGE_TRAVEL_SPEED_KMH: float = 25.0

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"