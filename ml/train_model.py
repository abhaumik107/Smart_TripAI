"""
ml/train_model.py
==================
Scaffold for training a scikit-learn regression model that predicts the
same personalized_score currently produced by ``WeightedScorer``.

This is intentionally a *standalone, offline* script (run manually, not at
request time) because in a real product you would train this against
historical user engagement data (e.g. "did the user actually visit /
favorite this recommended attraction?"), not synthetic data. Today, no such
labeled dataset exists yet, so this script:

1. Generates synthetic training examples using WeightedScorer as a
   "teacher" signal (a standard bootstrapping technique when no real
   labels exist yet).
2. Trains a RandomForestRegressor to approximate that function.
3. Saves the trained model to data/scorer_model.joblib.

``MLScorer`` below loads that artifact and satisfies the exact same
``BaseScorer`` interface as ``WeightedScorer``, so services/optimizer.py
can switch strategies with a single line change once real engagement data
justifies retraining on it.

Run directly:
    python -m ml.train_model
"""

import random
from pathlib import Path
from typing import List, Set, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

import config
from api.places import Attraction
from ml.scorer import BaseScorer, WeightedScorer
from utils.helpers import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "scorer_model.joblib"

FEATURE_NAMES = ["rating", "review_count_log", "interest_match"]


def _build_feature_vector(attraction: Attraction, user_interests: Set[str]) -> List[float]:
    """Convert an Attraction + interest set into a numeric feature vector.

    Kept separate from WeightedScorer's internal normalization so the ML
    pipeline has its own explicit, versioned feature contract -- changing
    how WeightedScorer normalizes values should not silently change what
    features the trained model expects.
    """
    review_count_log = np.log1p(max(attraction.review_count, 0))
    interest_match = 1.0 if any(
        attraction.category in config.INTEREST_CATEGORY_MAP.get(i, [])
        for i in user_interests
    ) else 0.0
    return [attraction.rating, review_count_log, interest_match]


def _generate_synthetic_dataset(num_samples: int = 2000) -> Tuple[np.ndarray, np.ndarray]:
    """Generate synthetic (features, label) pairs using WeightedScorer as
    a bootstrapping "teacher" signal.

    Replace this function with a loader over real historical
    user-interaction data once available -- the rest of this script does
    not need to change.
    """
    rng = random.Random(7)
    teacher = WeightedScorer()
    categories = [c for cats in config.INTEREST_CATEGORY_MAP.values() for c in cats]

    X, y = [], []
    for _ in range(num_samples):
        attraction = Attraction(
            place_id="synthetic",
            name="synthetic",
            latitude=0.0,
            longitude=0.0,
            rating=round(rng.uniform(1.0, 5.0), 1),
            review_count=rng.randint(0, 20000),
            category=rng.choice(categories),
            address="",
        )
        user_interests = set(
            rng.sample(config.ALL_INTERESTS, k=rng.randint(1, 3))
        )
        label = teacher.score(attraction, user_interests)
        X.append(_build_feature_vector(attraction, user_interests))
        y.append(label)

    return np.array(X), np.array(y)


def train_and_save_model() -> None:
    """Train a RandomForestRegressor and persist it to MODEL_PATH."""
    logger.info("Generating synthetic training dataset...")
    X, y = _generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    logger.info("Training RandomForestRegressor on %d samples...", len(X_train))
    model = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    score = model.score(X_test, y_test)
    logger.info("Validation R^2 score: %.4f", score)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info("Model saved to %s", MODEL_PATH)


class MLScorer(BaseScorer):
    """Scikit-learn-backed scorer satisfying the same BaseScorer contract
    as WeightedScorer.

    Loads the trained model lazily so importing this module never requires
    a model artifact to already exist (e.g. in fresh clones / CI).
    """

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"No trained model found at {model_path}. "
                "Run `python -m ml.train_model` first."
            )
        self.model = joblib.load(model_path)

    def score(self, attraction: Attraction, user_interests: Set[str]) -> float:
        features = np.array([_build_feature_vector(attraction, user_interests)])
        prediction = float(self.model.predict(features)[0])
        return round(min(max(prediction, 0.0), 1.0), 4)


if __name__ == "__main__":
    train_and_save_model()
