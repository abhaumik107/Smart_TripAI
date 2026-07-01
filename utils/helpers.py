# helpers.py - shared utilities: logging, geometry, formatting

import logging
import math
from functools import lru_cache
from typing import Tuple

import config


def get_logger(name: str) -> logging.Logger:
    # consistent logger across all modules, no duplicate handlers
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(config.LOG_LEVEL)
        logger.propagate = False
    return logger


@lru_cache(maxsize=4096)
def haversine_distance_km(point_a: Tuple[float, float], point_b: Tuple[float, float]) -> float:
    # cached great-circle distance — repeated (A,B) pairs are O(1) after first call
    lat1, lon1 = point_a
    lat2, lon2 = point_b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def km_to_minutes(distance_km: float, speed_kmh: float = config.AVERAGE_TRAVEL_SPEED_KMH) -> float:
    # convert km to travel minutes at configured urban speed
    if speed_kmh <= 0:
        raise ValueError("speed_kmh must be positive")
    return (distance_km / speed_kmh) * 60.0


def format_minutes_as_hours_text(minutes: float) -> str:
    # e.g. 90 → "1h 30m", 60 → "1h", 45 → "45m"
    minutes = max(0, round(minutes))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


def round_up_to_block(minutes: float, block_size: int = config.TIME_BLOCK_MINUTES) -> int:
    # round up to nearest block so knapsack never under-counts visit time
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    return int(math.ceil(minutes / block_size) * block_size)