# SmartTrip AI

A personalized, time-optimized travel itinerary planner built around two
real algorithmic cores — a **0/1 Knapsack dynamic program** and a
**nearest-neighbor route heuristic** — plus a pluggable **recommendation
engine** designed to be swapped from a transparent weighted formula to a
trained scikit-learn model without touching the rest of the system.

## Why this project exists

Most "travel planner" demos just call an LLM and format the output. This
project instead treats itinerary planning as what it actually is: a
constrained optimization problem (limited time, many candidate
attractions, each with a cost and a value) solved with a real, manually
implemented dynamic programming algorithm — the same class of problem as
classic resource-allocation knapsack problems, applied to a genuine
product use case.

## How it works

```
User input (city, start location, hours, interests)
        │
        ▼
Google Places API  (or MOCK_MODE synthetic data if no API key is set)
        │
        ▼
Preprocessing  →  clean data, assign estimated visit durations
        │
        ▼
Recommendation Engine (WeightedScorer)
   final_score = 0.45·rating + 0.25·popularity + 0.30·interest_match
        │
        ▼
0/1 Knapsack DP
   weight = visit duration (discretized into time blocks)
   value  = personalized_score
   capacity = available time minus a reserved travel-time buffer
        │
        ▼
Nearest-Neighbor Route Builder
   sequences the selected attractions starting from the user's location
        │
        ▼
Feasibility trim
   if real travel time exceeds the reserved buffer, drop the weakest
   score-per-minute attraction and re-route, repeating until feasible
        │
        ▼
Streamlit Dashboard  →  map, timeline, attraction cards, summary metrics
```

### A note on algorithm choice

An earlier draft of this project planned to use Dijkstra's shortest-path
algorithm over the attraction graph. That was dropped deliberately: with a
small, fully-connected set of attractions and straight-line travel-time
estimates, every shortest path between two nodes *is* the direct edge, so
Dijkstra would have added algorithmic theater without real value. Instead,
travel time is computed directly from a Haversine-distance matrix, and the
real algorithmic depth lives in the Knapsack DP (an honestly NP-hard
combinatorial optimization, solved exactly via DP) and the route-building
heuristic (an honestly-acknowledged heuristic for an NP-hard TSP-path
problem, not pretended to be exact).

### Why Knapsack DP can't model travel time directly

0/1 Knapsack assumes each item has an independent weight. But the real
travel cost of visiting attraction *C* depends on what you visited before
it — which the DP can't represent without becoming a much harder combined
knapsack+routing problem. This project resolves that honestly with a
two-phase design:

1. The **DP optimizes visiting time only**, against a capacity that
   already reserves a buffer (default 25%) for travel.
2. The **route builder computes real travel time** for the chosen set.
3. A **trimming step** removes the weakest score-per-minute attraction and
   re-routes if the real travel time overshoots the buffer.

The DP's optimality guarantee is honestly scoped to step 1; step 3 is
documented as a practical feasibility correction, not claimed as part of
the DP's optimality proof.

## Project structure

```
SmartTripAI/
├── app.py                    # Streamlit UI entry point
├── config.py                 # Central configuration & constants
├── requirements.txt
├── .env.example
├── api/
│   └── places.py             # Google Places client + MOCK_MODE fallback
├── algorithms/
│   ├── knapsack.py           # Manual 0/1 Knapsack DP
│   └── route_builder.py      # Nearest-neighbor route heuristic
├── ml/
│   ├── scorer.py              # BaseScorer / WeightedScorer (Strategy pattern)
│   └── train_model.py         # Scikit-learn MLScorer training scaffold
├── services/
│   ├── preprocessing.py       # Data cleaning & duration assignment
│   └── optimizer.py           # Orchestrates the full pipeline
├── utils/
│   └── helpers.py             # Logging, Haversine distance, formatting
├── tests/
│   ├── test_knapsack.py
│   └── test_route_builder.py
└── data/                       # Trained model artifacts land here
```

## Running it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Optionally set GOOGLE_PLACES_API_KEY in .env for live data.
# Leave it blank to run in MOCK_MODE with synthetic attractions.

streamlit run app.py
```

Run the test suite:

```bash
pytest tests/
```

Train the ML scorer (optional — currently bootstrapped from synthetic
data; swap in real engagement logs when available):

```bash
python -m ml.train_model
```

## Swapping in the ML scorer

```python
from ml.train_model import MLScorer
from services.optimizer import TripOptimizer

optimizer = TripOptimizer(scorer=MLScorer())
```

No other code changes — `services/optimizer.py` depends only on the
`BaseScorer` interface.

## Design principles

- **Single responsibility per module** — Places fetching, preprocessing,
  scoring, DP optimization, routing, and orchestration are all separate,
  independently testable units.
- **No external optimization libraries** — Knapsack DP and the
  nearest-neighbor route builder are implemented from scratch.
- **Honest algorithmic framing** — every guarantee and every heuristic's
  limitations are documented where the trade-off is made, not glossed
  over.
- **MOCK_MODE** — the entire pipeline runs end-to-end without any paid API
  key, which makes the project trivially demoable and CI-testable.
