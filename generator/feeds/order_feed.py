"""
order_feed.py — Generates Order Lifecycle Events for the food delivery stream.

Each call to generate_order_events() produces the full sequence of state-transition
events for a single order, including intentional edge-case injections.
"""

import uuid
import random
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    """Wall-clock time in epoch milliseconds."""
    return int(time.time() * 1000)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _build_event(
    order_id: str,
    event_type: str,
    event_time_ms: int,
    customer_id: str,
    restaurant_id: str,
    zone_id: str,
    order_value_eur: float,
    item_count: int,
    promo_applied: bool,
    device_id: str,
    courier_id: Optional[str] = None,
    promo_code: Optional[str] = None,
    cancellation_reason: Optional[str] = None,
    is_anomaly: bool = False,
) -> Dict[str, Any]:
    """Construct a single OrderLifecycleEvent dict matching the AVRO schema."""
    ingestion_delay_ms = random.randint(50, 800)  # simulate small broker ingestion lag
    return {
        "event_id":            str(uuid.uuid4()),
        "order_id":            order_id,
        "event_type":          event_type,
        "event_time":          event_time_ms,
        "ingestion_time":      event_time_ms + ingestion_delay_ms,
        "customer_id":         customer_id,
        "restaurant_id":       restaurant_id,
        "courier_id":          courier_id,
        "zone_id":             zone_id,
        "order_value_eur":     round(order_value_eur, 2),
        "item_count":          item_count,
        "promo_applied":       promo_applied,
        "promo_code":          promo_code,
        "cancellation_reason": cancellation_reason,
        "device_id":           device_id,
        "is_anomaly":          is_anomaly,
        "schema_version":      "1.0",
    }


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_order_events(
    sim_start_ms: int,
    restaurants: List[str],
    couriers: List[str],
    customers: List[str],
    devices: Dict[str, str],
    zones: List[str],
    zone_weights: List[float],
    inject_anomalies: bool = True,
) -> List[Dict[str, Any]]:
    """
    Generate the full event sequence for a single order.

    Returns a list of OrderLifecycleEvent dicts ordered by event_time.
    May include duplicates and out-of-order events if inject_anomalies=True.
    """
    events: List[Dict[str, Any]] = []

    order_id      = str(uuid.uuid4())
    restaurant_id = random.choice(restaurants)
    customer_id   = random.choice(customers)
    device_id     = devices[customer_id]
    zone_id       = random.choices(zones, weights=zone_weights, k=1)[0]

    # Order value + items
    order_value = max(
        config.ORDER_VALUE_MIN_EUR,
        random.gauss(config.ORDER_VALUE_MEAN_EUR, config.ORDER_VALUE_STD_EUR)
    )
    item_count = random.randint(1, 8)

    # Promo
    promo_applied = random.random() < config.PROMO_PROBABILITY
    promo_code    = f"PROMO{random.randint(10, 99)}" if promo_applied else None

    # PLACED timestamp — relative to sim_start with some jitter
    t = sim_start_ms + random.randint(0, 60_000)

    courier_id: Optional[str] = None
    is_cancelled = random.random() < config.CANCELLATION_PROBABILITY

    # -----------------------------------------------------------------------
    # State machine
    # -----------------------------------------------------------------------
    # 1. PLACED
    events.append(_build_event(
        order_id=order_id, event_type="PLACED", event_time_ms=t,
        customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
        order_value_eur=order_value, item_count=item_count,
        promo_applied=promo_applied, device_id=device_id, promo_code=promo_code,
    ))

    if is_cancelled and random.random() < 0.3:
        # Cancel immediately after placement
        t += random.randint(10_000, 120_000)
        events.append(_build_event(
            order_id=order_id, event_type="CANCELLED", event_time_ms=t,
            customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
            order_value_eur=order_value, item_count=item_count,
            promo_applied=promo_applied, device_id=device_id,
            cancellation_reason="CUSTOMER_REQUEST",
        ))
        return _maybe_inject_anomalies(events, inject_anomalies)

    # 2. ACCEPTED
    t += random.randint(30_000, 180_000)  # 30s–3min acceptance delay
    courier_id = random.choice(couriers)
    events.append(_build_event(
        order_id=order_id, event_type="ACCEPTED", event_time_ms=t,
        customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
        order_value_eur=order_value, item_count=item_count,
        promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
    ))

    # 3. PREPARING
    t += random.randint(10_000, 60_000)
    events.append(_build_event(
        order_id=order_id, event_type="PREPARING", event_time_ms=t,
        customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
        order_value_eur=order_value, item_count=item_count,
        promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
    ))

    if is_cancelled and random.random() < 0.3:
        t += random.randint(30_000, 120_000)
        events.append(_build_event(
            order_id=order_id, event_type="CANCELLED", event_time_ms=t,
            customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
            order_value_eur=order_value, item_count=item_count,
            promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
            cancellation_reason="RESTAURANT_UNAVAILABLE",
        ))
        return _maybe_inject_anomalies(events, inject_anomalies)

    # 4. READY_FOR_PICKUP
    prep_seconds = max(60, random.gauss(config.PREP_TIME_MEAN_SECONDS, config.PREP_TIME_STD_SECONDS))
    t += int(prep_seconds * 1000)
    events.append(_build_event(
        order_id=order_id, event_type="READY_FOR_PICKUP", event_time_ms=t,
        customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
        order_value_eur=order_value, item_count=item_count,
        promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
    ))

    # 5. PICKED_UP — optionally skip (missing-step anomaly injected later)
    missing_pickup = inject_anomalies and (random.random() < config.ANOMALY_MISSING_STEP_RATE)
    courier_offline = inject_anomalies and (random.random() < config.ANOMALY_COURIER_OFFLINE_RATE)

    if not missing_pickup:
        t += random.randint(60_000, 600_000)  # 1–10 min wait for courier
        events.append(_build_event(
            order_id=order_id, event_type="PICKED_UP", event_time_ms=t,
            customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
            order_value_eur=order_value, item_count=item_count,
            promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
        ))

    if courier_offline:
        # Courier goes offline — no DELIVERED event, ends with CANCELLED
        t += random.randint(120_000, 600_000)
        events.append(_build_event(
            order_id=order_id, event_type="CANCELLED", event_time_ms=t,
            customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
            order_value_eur=order_value, item_count=item_count,
            promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
            cancellation_reason="COURIER_TIMEOUT",
            is_anomaly=True,
        ))
        return _maybe_inject_anomalies(events, inject_anomalies)

    # 6. DELIVERED
    delivery_seconds = max(60, random.gauss(config.DELIVERY_TIME_MEAN_SECONDS, config.DELIVERY_TIME_STD_SECONDS))
    t += int(delivery_seconds * 1000)
    events.append(_build_event(
        order_id=order_id, event_type="DELIVERED", event_time_ms=t,
        customer_id=customer_id, restaurant_id=restaurant_id, zone_id=zone_id,
        order_value_eur=order_value, item_count=item_count,
        promo_applied=promo_applied, device_id=device_id, courier_id=courier_id,
        is_anomaly=missing_pickup,  # flag if we skipped PICKED_UP
    ))

    return _maybe_inject_anomalies(events, inject_anomalies)


# ---------------------------------------------------------------------------
# Anomaly injectors
# ---------------------------------------------------------------------------

def _maybe_inject_anomalies(events: List[Dict], inject: bool) -> List[Dict]:
    """Apply out-of-order delays and duplicate injection to an event list."""
    if not inject:
        return events

    result = []
    for ev in events:
        # Out-of-order: delay event_time backwards (late arrival)
        if random.random() < config.ANOMALY_OUT_OF_ORDER_RATE:
            delay_ms = random.randint(1000, config.ANOMALY_OUT_OF_ORDER_MAX_DELAY_SECONDS * 1000)
            ev = dict(ev)
            ev["event_time"] -= delay_ms
            ev["is_anomaly"] = True

        result.append(ev)

        # Duplicate: re-emit same event with new event_id but same order/type
        if random.random() < config.ANOMALY_DUPLICATE_RATE:
            dup = dict(ev)
            dup["event_id"] = str(uuid.uuid4())   # new event_id
            dup["ingestion_time"] = ev["ingestion_time"] + random.randint(100, 5000)
            dup["is_anomaly"] = True
            result.append(dup)

    return result
