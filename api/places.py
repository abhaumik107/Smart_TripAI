# places.py - hits Google Places API (or fakes it) to get nearby attractions
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

import config
from utils.helpers import get_logger

logger = get_logger(__name__)

# Google Places types that should never appear in a travel itinerary
# checked against the full types[] array each result returns — catches hotels/banks
# tagged as tourist_attraction, establishment, point_of_interest etc.
_BLOCKED_PLACE_TYPES = {
    "lodging",                  # hotels, hostels, motels, B&Bs
    "bank", "atm", "finance",   # banks and ATMs
    "real_estate_agency",
    "insurance_agency",
    "gas_station", "car_repair", "car_dealer", "car_wash", "car_rental",
    "laundry", "hair_care", "beauty_salon",
    "gym", "physiotherapist",
    "hospital", "doctor", "dentist", "pharmacy", "veterinary_care",
    "funeral_home", "storage",
    "transit_station", "bus_station", "subway_station", "taxi_stand",
}


@dataclass
class Attraction:
    # single POI passed through the whole pipeline
    place_id: str
    name: str
    latitude: float
    longitude: float
    rating: float
    review_count: int
    category: str
    address: str

    # filled in later by scoring/preprocessing stages
    visit_duration_minutes: int = field(default=0)
    personalized_score: float = field(default=0.0)
    price_level: int = field(default=-1)  # 0=free 1=cheap 2=moderate 3=expensive; -1=unknown


class GeocodingError(Exception):
    # thrown when a location string can't be turned into coords
    pass


class PlacesAPIError(Exception):
    # thrown when Google Places returns an error
    pass


class PlacesClient:
    # wraps geocoding + nearby search; auto-switches to mock if no API key

    def __init__(self, api_key: str = config.GOOGLE_PLACES_API_KEY) -> None:
        self.api_key = api_key
        self.mock_mode = config.MOCK_MODE
        if self.mock_mode:
            logger.warning(
                "GOOGLE_PLACES_API_KEY not set - PlacesClient running in MOCK_MODE. "
                "Synthetic attraction data will be generated instead of live API calls."
            )

    def geocode(self, location_text: str, city: Optional[str] = None) -> Tuple[float, float]:
        # turns "Gateway of India" into (lat, lon)
        if self.mock_mode:
            return self._mock_geocode(location_text)

        query = f"{location_text}, {city}" if city else location_text
        params = {"address": query, "key": self.api_key}

        try:
            response = requests.get(config.GOOGLE_GEOCODE_URL, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Geocoding request failed for '%s': %s", query, exc)
            raise GeocodingError(f"Network error while geocoding '{query}'") from exc

        data = response.json()
        if data.get("status") != "OK" or not data.get("results"):
            logger.error("Geocoding failed for '%s': %s", query, data.get("status"))
            raise GeocodingError(f"Could not geocode location '{query}'")

        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]

    @staticmethod
    def _mock_geocode(location_text: str) -> Tuple[float, float]:
        # hash the input string so same text always gives same coords
        seed = sum(ord(c) for c in location_text.lower())
        rng = random.Random(seed)
        base_lat, base_lon = 19.0760, 72.8777  # Mumbai as mock anchor
        lat = base_lat + rng.uniform(-0.03, 0.03)
        lon = base_lon + rng.uniform(-0.03, 0.03)
        return lat, lon

    def fetch_nearby_attractions(
        self,
        center: Tuple[float, float],
        categories: List[str],
        radius_meters: int = config.PLACES_SEARCH_RADIUS_METERS,
        max_results: int = config.PLACES_MAX_RESULTS,
    ) -> List[Attraction]:
        # fetches POIs around center for each category, deduped by place_id
        if self.mock_mode:
            return self._mock_attractions(center, categories, radius_meters, max_results)

        seen_place_ids: set = set()
        seen_names: set = set()  # normalized chain name dedup e.g. "monginis" across all branches
        results: List[Attraction] = []

        for category in dict.fromkeys(categories):
            params = {
                "location": f"{center[0]},{center[1]}",
                "radius": radius_meters,
                "type": category,
                "key": self.api_key,
            }
            # inject keyword hint so Google returns heritage/landmark results
            # instead of generic commercial places for vague types like tourist_attraction
            keyword = config.CATEGORY_KEYWORDS.get(category)
            if keyword:
                params["keyword"] = keyword
            try:
                response = requests.get(
                    config.GOOGLE_NEARBY_SEARCH_URL, params=params, timeout=10
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Places search failed for category '%s': %s", category, exc)
                continue

            data = response.json()
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                logger.warning(
                    "Places API returned status '%s' for category '%s'",
                    data.get("status"),
                    category,
                )
                continue

            for place in data.get("results", []):
                place_id = place.get("place_id")
                if not place_id or place_id in seen_place_ids:
                    continue

                # check ALL types Google assigned to this place — a hotel tagged as
                # tourist_attraction still has "lodging" in its types list
                # this is the global fix: no brand names needed, works for any city
                place_types = set(place.get("types", []))
                if place_types & _BLOCKED_PLACE_TYPES:
                    continue

                # skip cheap/fast-food tier places (price_level 0 or 1)
                price_level = place.get("price_level", -1)
                if price_level != -1 and price_level <= 1:
                    continue

                # deduplicate chain brands by normalized name
                normalized_name = place.get("name", "").strip().lower()
                if normalized_name in seen_names:
                    continue

                seen_place_ids.add(place_id)
                seen_names.add(normalized_name)

                location = place.get("geometry", {}).get("location", {})
                results.append(
                    Attraction(
                        place_id=place_id,
                        name=place.get("name", "Unknown"),
                        latitude=location.get("lat", center[0]),
                        longitude=location.get("lng", center[1]),
                        rating=float(place.get("rating", 0.0) or 0.0),
                        review_count=int(place.get("user_ratings_total", 0) or 0),
                        category=category,
                        address=place.get("vicinity", ""),
                        price_level=price_level,
                    )
                )

                if len(results) >= max_results:
                    return results

        return results

    @staticmethod
    def _mock_attractions(
        center: Tuple[float, float],
        categories: List[str],
        radius_meters: int,
        max_results: int,
    ) -> List[Attraction]:
        # generates fake attractions scattered properly across the configured radius
        rng = random.Random(42)
        center_lat, center_lon = center
        meters_per_deg_lat = 111_320.0
        meters_per_deg_lon = 111_320.0 * max(math.cos(math.radians(center_lat)), 0.1)

        name_templates = {
            "museum": ["City History Museum", "Modern Art Museum", "Heritage Museum"],
            "art_gallery": ["Downtown Art Gallery", "Contemporary Gallery"],
            "historical_landmark": ["Old Fort", "Colonial Landmark", "Heritage Tower"],
            "monument": ["Independence Monument", "War Memorial"],
            "place_of_worship": ["Grand Temple", "Old Cathedral"],
            "park": ["Central Park", "Riverside Garden", "Botanical Park"],
            "natural_feature": ["Scenic Viewpoint", "Coastal Trail"],
            "zoo": ["City Zoo"],
            "botanical_garden": ["Botanical Gardens"],
            "restaurant": ["Spice Route Restaurant", "Harbor Bistro", "Local Thali House"],
            "cafe": ["Corner Cafe", "Roastery Coffee House"],
            "bakery": ["Sunrise Bakery"],
            "shopping_mall": ["Grand Shopping Mall", "City Center Mall"],
            "store": ["Artisan Market Store"],
            "market": ["Old Town Market", "Night Bazaar"],
            "bar": ["Rooftop Bar", "Speakeasy Lounge"],
            "night_club": ["Pulse Nightclub"],
            "amusement_park": ["Wonderland Amusement Park"],
            "movie_theater": ["Grand Cinema"],
            "tourist_attraction": ["Famous City Tower", "Iconic Skywalk"],
        }

        results: List[Attraction] = []
        seen_mock_ids: set = set()  # prevent same place_id appearing under multiple categories
        for category in dict.fromkeys(categories):
            templates = name_templates.get(category, [f"{category.title()} Spot"])
            for name in templates:
                if len(results) >= max_results:
                    return results

                # sqrt keeps distribution uniform over area, not biased to center
                place_id = f"mock_{category}_{name.replace(' ', '_').lower()}"
                if place_id in seen_mock_ids:
                    continue
                seen_mock_ids.add(place_id)

                angle = rng.uniform(0, 2 * math.pi)
                distance_m = math.sqrt(rng.uniform(0.05, 1.0)) * radius_meters

                lat = center_lat + (distance_m * math.cos(angle)) / meters_per_deg_lat
                lon = center_lon + (distance_m * math.sin(angle)) / meters_per_deg_lon

                results.append(
                    Attraction(
                        place_id=place_id,
                        name=name,
                        latitude=lat,
                        longitude=lon,
                        rating=round(rng.uniform(3.5, 4.9), 1),
                        review_count=rng.randint(50, 5000),
                        category=category,
                        address=f"{rng.randint(1, 200)} {name} Street",
                    )
                )
        return results
