"""
config.py — Centralised configuration for the food-delivery stream generator.

All parameters can be overridden via CLI flags in generate.py.
Defaults represent a moderate 1-hour lunch rush simulation.
"""

from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Zone definitions
# ---------------------------------------------------------------------------
DEFAULT_ZONES = ["ZONE_CENTRO", "ZONE_NORTH", "ZONE_SOUTH", "ZONE_EAST", "ZONE_WEST"]

# Zone-level demand skew weights (higher = more orders generated in that zone).
# Must sum to 1.0 or will be normalised automatically.
ZONE_DEMAND_WEIGHTS = {
    "ZONE_CENTRO": 0.40,   # City centre — highest demand
    "ZONE_NORTH":  0.20,
    "ZONE_SOUTH":  0.15,
    "ZONE_EAST":   0.15,
    "ZONE_WEST":   0.10,
}

# ---------------------------------------------------------------------------
# Time / simulation settings
# ---------------------------------------------------------------------------
# Simulation operates in "accelerated time": real seconds map to simulated minutes.
# This means a 60-minute rush can be generated in ~60 seconds of wall time.
SIMULATION_START_HOUR = 12          # 12:00 — start of lunch peak
SIMULATION_DURATION_MINUTES = 60    # How many simulated minutes to generate

# Traffic multipliers by simulated hour of day (keys = hour 0-23)
HOURLY_DEMAND_MULTIPLIER = {
    0: 0.05, 1: 0.02, 2: 0.02, 3: 0.02, 4: 0.02, 5: 0.05,
    6: 0.10, 7: 0.20, 8: 0.30, 9: 0.30, 10: 0.35, 11: 0.70,
    12: 1.00,  # Lunch peak
    13: 0.95,
    14: 0.70,
    15: 0.50, 16: 0.45, 17: 0.55, 18: 0.75,
    19: 1.00,  # Dinner peak
    20: 0.95,
    21: 0.80,
    22: 0.50, 23: 0.20,
}

# Weekend multiplier (applied on top of hourly multiplier)
WEEKEND_DEMAND_MULTIPLIER = 1.25

# ---------------------------------------------------------------------------
# Platform entities
# ---------------------------------------------------------------------------
NUM_RESTAURANTS = 20
NUM_COURIERS    = 40
NUM_CUSTOMERS   = 500
NUM_ZONES       = 3           # Subset of DEFAULT_ZONES to activate

# ---------------------------------------------------------------------------
# Order behaviour probabilities
# ---------------------------------------------------------------------------
CANCELLATION_PROBABILITY    = 0.07   # Base probability an order is cancelled at any stage
PROMO_PROBABILITY           = 0.20   # Fraction of orders with a promo applied
SURGE_PROBABILITY           = 0.10   # Probability a demand surge starts in any given window

# Prep time distributions (seconds), normal distribution params
PREP_TIME_MEAN_SECONDS      = 600    # 10 minutes average
PREP_TIME_STD_SECONDS       = 180    # ±3 minutes std dev
SLA_THRESHOLD_SECONDS       = 900    # 15 minutes SLA for standard restaurants
PARTNER_SLA_THRESHOLD_SECONDS = 720  # 12 minutes for partner restaurants
PARTNER_RESTAURANT_FRACTION = 0.30   # 30% of restaurants are partners

# Delivery time distributions (seconds after pickup)
DELIVERY_TIME_MEAN_SECONDS  = 1200   # 20 minutes average
DELIVERY_TIME_STD_SECONDS   = 300    # ±5 minutes

# Order value distribution (EUR)
ORDER_VALUE_MEAN_EUR        = 22.50
ORDER_VALUE_STD_EUR         = 9.00
ORDER_VALUE_MIN_EUR         = 5.00

# ---------------------------------------------------------------------------
# Edge-case injection rates (streaming correctness tests)
# ---------------------------------------------------------------------------
ANOMALY_OUT_OF_ORDER_RATE   = 0.05   # 5% of events delayed to simulate late arrival
ANOMALY_OUT_OF_ORDER_MAX_DELAY_SECONDS = 480  # Max 8-minute delay
ANOMALY_DUPLICATE_RATE      = 0.02   # 2% of events re-emitted as duplicates
ANOMALY_MISSING_STEP_RATE   = 0.01   # 1% of orders skip PICKED_UP before DELIVERED
ANOMALY_IMPOSSIBLE_DURATION_RATE = 0.005  # 0.5% of prep events get duration > 3600s
ANOMALY_COURIER_OFFLINE_RATE = 0.02  # 2% of couriers "go offline" mid-delivery

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------
OUTPUT_FORMAT = "both"               # "json" | "avro" | "both"
OUTPUT_DIR    = "sample_data"
JSON_INDENT   = 2                    # Pretty-print JSON (set None for compact)
