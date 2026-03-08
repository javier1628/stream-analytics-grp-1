"""
restaurant_feed.py — Generates Restaurant Events for the food delivery stream.

For each order that reaches the PREPARING stage, this generator produces the
corresponding kitchen milestones. It also emits capacity signals (RESTAURANT_BUSY /
RESTAURANT_AVAILABLE) independently of individual orders.
"""

import uuid
import random
import time
from typing import List, Dict, Any, Optional

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CUISINE_TYPES = ["PIZZA", "SUSHI", "BURGER", "SALAD", "PASTA", "INDIAN", "MEXICAN", "CHINESE", "OTHER"]

# Per-restaurant static metadata (generated once and reused)
_restaurant_meta: Dict[str, Dict] = {}


def init_restaurant_metadata(restaurant_ids: List[str]) -> None:
    """Pre-generate static attributes for each restaurant. Call once at startup."""
    global _restaurant_meta
    for rid in restaurant_ids:
        is_partner = random.random() < config.PARTNER_RESTAURANT_FRACTION
        _restaurant_meta[rid] = {
            "cuisine_type":       random.choice(CUISINE_TYPES),
            "is_partner":         is_partner,
            "sla_threshold":      config.PARTNER_SLA_THRESHOLD_SECONDS if is_partner
                                  else config.SLA_THRESHOLD_SECONDS,
            "zone_id":            None,  # assigned during generation
        }


def get_restaurant_zone(restaurant_id: str, zones: List[str], zone_weights: List[float]) -> str:
    """Assign (or recall) a fixed zone for a restaurant."""
    meta = _restaurant_meta.get(restaurant_id, {})
    if meta.get("zone_id") is None:
        zone = random.choices(zones, weights=zone_weights, k=1)[0]
        _restaurant_meta[restaurant_id]["zone_id"] = zone
    return _restaurant_meta[restaurant_id]["zone_id"]


def _build_event(
    restaurant_id: str,
    event_type: str,
    event_time_ms: int,
    zone_id: str,
    queue_depth: int,
    capacity_pct: float,
    order_id: Optional[str] = None,
    prep_duration_seconds: Optional[int] = None,
    is_anomaly: bool = False,
) -> Dict[str, Any]:
    """Construct a single RestaurantEvent dict matching the AVRO schema."""
    meta = _restaurant_meta.get(restaurant_id, {})
    ingestion_delay_ms = random.randint(50, 600)
    return {
        "event_id":               str(uuid.uuid4()),
        "order_id":               order_id,
        "restaurant_id":          restaurant_id,
        "event_type":             event_type,
        "event_time":             event_time_ms,
        "ingestion_time":         event_time_ms + ingestion_delay_ms,
        "zone_id":                zone_id,
        "prep_duration_seconds":  prep_duration_seconds,
        "sla_threshold_seconds":  meta.get("sla_threshold", config.SLA_THRESHOLD_SECONDS),
        "queue_depth":            queue_depth,
        "capacity_pct":           round(min(1.0, max(0.0, capacity_pct)), 3),
        "cuisine_type":           meta.get("cuisine_type", "OTHER"),
        "is_partner_restaurant":  meta.get("is_partner", False),
        "is_anomaly":             is_anomaly,
        "schema_version":         "1.0",
    }


# ---------------------------------------------------------------------------
# Per-order kitchen event sequence
# ---------------------------------------------------------------------------

def generate_kitchen_events(
    order_id: str,
    restaurant_id: str,
    zone_id: str,
    order_accepted_time_ms: int,
    inject_anomalies: bool = True,
) -> List[Dict[str, Any]]:
    """
    Generate the kitchen milestone sequence for one order:
      ORDER_RECEIVED → PREP_STARTED → PREP_COMPLETE → HANDOFF_TO_COURIER
      (+ optional SLA_BREACH)

    Returns events sorted by event_time.
    """
    events: List[Dict] = []
    meta = _restaurant_meta.get(restaurant_id, {})
    sla = meta.get("sla_threshold", config.SLA_THRESHOLD_SECONDS)

    # Simulate current queue depth (random; in a real system this would be stateful)
    queue_depth  = random.randint(1, 12)
    capacity_pct = min(1.0, queue_depth / 10.0 + random.gauss(0, 0.05))

    t = order_accepted_time_ms

    # 1. ORDER_RECEIVED — slight delay after platform ACCEPTED event
    t += random.randint(5_000, 30_000)
    events.append(_build_event(
        restaurant_id=restaurant_id, event_type="ORDER_RECEIVED",
        event_time_ms=t, zone_id=zone_id,
        queue_depth=queue_depth, capacity_pct=capacity_pct,
        order_id=order_id,
    ))

    # 2. PREP_STARTED
    t += random.randint(10_000, 90_000)
    prep_start_ms = t
    events.append(_build_event(
        restaurant_id=restaurant_id, event_type="PREP_STARTED",
        event_time_ms=t, zone_id=zone_id,
        queue_depth=queue_depth, capacity_pct=capacity_pct,
        order_id=order_id,
    ))

    # 3. Determine prep duration — possibly anomalous
    impossible_duration = inject_anomalies and (
        random.random() < config.ANOMALY_IMPOSSIBLE_DURATION_RATE
    )
    if impossible_duration:
        prep_seconds = random.randint(3700, 7200)  # > 1 hour — clearly impossible
    else:
        prep_seconds = max(60, int(random.gauss(config.PREP_TIME_MEAN_SECONDS,
                                                config.PREP_TIME_STD_SECONDS)))

    t += prep_seconds * 1000

    # 4. SLA_BREACH — emit before PREP_COMPLETE if threshold exceeded
    if prep_seconds > sla:
        sla_breach_time = prep_start_ms + sla * 1000
        events.append(_build_event(
            restaurant_id=restaurant_id, event_type="SLA_BREACH",
            event_time_ms=sla_breach_time, zone_id=zone_id,
            queue_depth=queue_depth, capacity_pct=capacity_pct,
            order_id=order_id, is_anomaly=impossible_duration,
        ))

    # 5. PREP_COMPLETE
    events.append(_build_event(
        restaurant_id=restaurant_id, event_type="PREP_COMPLETE",
        event_time_ms=t, zone_id=zone_id,
        queue_depth=max(0, queue_depth - 1),
        capacity_pct=max(0.0, capacity_pct - 0.08),
        order_id=order_id,
        prep_duration_seconds=prep_seconds,
        is_anomaly=impossible_duration,
    ))

    # 6. HANDOFF_TO_COURIER
    t += random.randint(10_000, 120_000)
    events.append(_build_event(
        restaurant_id=restaurant_id, event_type="HANDOFF_TO_COURIER",
        event_time_ms=t, zone_id=zone_id,
        queue_depth=max(0, queue_depth - 1),
        capacity_pct=max(0.0, capacity_pct - 0.08),
        order_id=order_id,
    ))

    # Apply out-of-order / duplicate anomalies
    if inject_anomalies:
        events = _apply_stream_anomalies(events)

    return sorted(events, key=lambda e: e["event_time"])


# ---------------------------------------------------------------------------
# Capacity signal generator (not tied to individual orders)
# ---------------------------------------------------------------------------

def generate_capacity_signals(
    restaurant_id: str,
    zone_id: str,
    sim_start_ms: int,
    sim_duration_ms: int,
    num_signals: int = 5,
) -> List[Dict[str, Any]]:
    """
    Generate periodic RESTAURANT_BUSY / RESTAURANT_AVAILABLE capacity signals
    for a restaurant over the simulation window. These are independent of
    individual orders and represent aggregate capacity state.
    """
    events: List[Dict] = []
    interval_ms = sim_duration_ms // (num_signals + 1)
    is_busy = False

    for i in range(num_signals):
        t = sim_start_ms + interval_ms * (i + 1) + random.randint(-30_000, 30_000)
        is_busy = not is_busy
        queue_depth  = random.randint(8, 15) if is_busy else random.randint(0, 4)
        capacity_pct = random.uniform(0.7, 1.0) if is_busy else random.uniform(0.1, 0.4)
        event_type   = "RESTAURANT_BUSY" if is_busy else "RESTAURANT_AVAILABLE"

        events.append(_build_event(
            restaurant_id=restaurant_id, event_type=event_type,
            event_time_ms=t, zone_id=zone_id,
            queue_depth=queue_depth, capacity_pct=capacity_pct,
            order_id=None,
        ))

    return events


# ---------------------------------------------------------------------------
# Anomaly injectors
# ---------------------------------------------------------------------------

def _apply_stream_anomalies(events: List[Dict]) -> List[Dict]:
    """Apply out-of-order delays and duplicate injection."""
    result = []
    for ev in events:
        if random.random() < config.ANOMALY_OUT_OF_ORDER_RATE:
            delay_ms = random.randint(1000, config.ANOMALY_OUT_OF_ORDER_MAX_DELAY_SECONDS * 1000)
            ev = dict(ev)
            ev["event_time"] -= delay_ms
            ev["is_anomaly"] = True
        result.append(ev)

        if random.random() < config.ANOMALY_DUPLICATE_RATE:
            dup = dict(ev)
            dup["event_id"]       = str(uuid.uuid4())
            dup["ingestion_time"] = ev["ingestion_time"] + random.randint(100, 3000)
            dup["is_anomaly"]     = True
            result.append(dup)

    return result
