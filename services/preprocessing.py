# preprocessing.py - clean, deduplicate, and prep attractions before scoring

from typing import Dict, List, Set
import config
from api.places import Attraction
from utils.helpers import get_logger

logger = get_logger(__name__)

# exact normalized names — only universally known fast-food chains, no city-specific brands
_CHAIN_BLOCKLIST: Set[str] = {
    "mcdonald's", "mcdonalds", "kfc", "subway", "domino's", "dominos",
    "pizza hut", "burger king", "starbucks", "dunkin", "dunkin donuts",
    "costa coffee", "papa john's", "taco bell", "wendy's", "popeyes",
    "five guys", "shake shack",
}

# generic substrings that indicate non-tourist places regardless of city or country
# deliberately NO brand names here — that's handled by the types[] check in places.py
_NAME_KEYWORD_BLOCKLIST: Set[str] = {
    "hotel", "hostel", "inn ", " inn", "motel", "lodge", "lodging",
    "suites", "guest house", "guesthouse", "serviced apartment",
    "cinema", "cinemas", "cineplex", "multiplex",
    " bank", "bank ", "atm ",
}

# Google Places types that are never useful in a travel itinerary
_CATEGORY_BLOCKLIST: Set[str] = {
    "lodging", "hotel", "motel", "hostel", "guest_house",
    "real_estate_agency", "insurance_agency", "bank", "atm",
    "gas_station", "car_repair", "car_dealer", "car_wash",
    "laundry", "hair_care", "beauty_salon", "gym", "physiotherapist",
    "hospital", "doctor", "dentist", "pharmacy", "veterinary_care",
    "movie_theater",  # capped separately below — one cinema max via Entertainment interest
}

# max attractions per category in the candidate pool — food/entertainment capped hard
_CATEGORY_DIVERSITY_CAP: Dict[str, int] = {
    "restaurant": 3,
    "cafe": 2,
    "bakery": 1,
    "bar": 2,
    "night_club": 1,
    "store": 2,
    "shopping_mall": 3,
    "market": 2,
    "movie_theater": 1,
    "amusement_park": 2,
}
_DEFAULT_CATEGORY_CAP = 8  # tourist/landmark categories need enough to fill multi-day trips

MIN_SCORE_THRESHOLD: float = 0.35  # relaxed slightly — scoring already filters quality
MIN_RATING: float = 3.65            # 3.8 was too aggressive, many legit tourist spots fall below


def _is_name_blocked(name: str) -> bool:
    # check if any blocklist keyword appears anywhere in the normalized name
    return any(kw in name for kw in _NAME_KEYWORD_BLOCKLIST)


def clean_attractions(attractions: List[Attraction]) -> List[Attraction]:
    # dedup by place_id + normalized name; block hotels, chains, cinemas by name keyword
    seen_ids: set = set()
    seen_names: set = set()
    category_counts: Dict[str, int] = {}
    cleaned: List[Attraction] = []

    for attraction in attractions:
        if attraction.place_id in seen_ids:
            continue
        if attraction.latitude == 0.0 and attraction.longitude == 0.0:
            continue
        if attraction.rating < MIN_RATING:
            continue
        if attraction.category in _CATEGORY_BLOCKLIST:
            continue

        normalized = attraction.name.strip().lower()

        if normalized in _CHAIN_BLOCKLIST:
            continue
        if _is_name_blocked(normalized):
            continue
        if normalized in seen_names:
            continue

        cap = _CATEGORY_DIVERSITY_CAP.get(attraction.category, _DEFAULT_CATEGORY_CAP)
        if category_counts.get(attraction.category, 0) >= cap:
            continue

        seen_ids.add(attraction.place_id)
        seen_names.add(normalized)
        category_counts[attraction.category] = category_counts.get(attraction.category, 0) + 1
        cleaned.append(attraction)

    dropped = len(attractions) - len(cleaned)
    if dropped:
        logger.info("Dropped %d invalid/hotel/chain/cinema/capped attractions.", dropped)

    return cleaned


def assign_visit_durations(attractions: List[Attraction]) -> List[Attraction]:
    # set visit duration based on category
    for attraction in attractions:
        attraction.visit_duration_minutes = config.DEFAULT_VISIT_DURATIONS.get(
            attraction.category,
            config.DEFAULT_VISIT_DURATION_MINUTES,
        )
    return attractions


def filter_by_min_score(attractions: List[Attraction]) -> List[Attraction]:
    # drop low-scoring attractions after scoring so knapsack only sees quality options
    filtered = [a for a in attractions if a.personalized_score >= MIN_SCORE_THRESHOLD]
    dropped = len(attractions) - len(filtered)
    if dropped:
        logger.info("Dropped %d attractions below min score threshold (%.2f).", dropped, MIN_SCORE_THRESHOLD)
    return filtered


def preprocess(attractions: List[Attraction]) -> List[Attraction]:
    attractions = clean_attractions(attractions)
    attractions = assign_visit_durations(attractions)
    logger.info("Preprocessing complete: %d attractions ready.", len(attractions))
    return attractions
