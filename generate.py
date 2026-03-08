#!/usr/bin/env python3
"""
generate.py — Entry point for the food-delivery stream event generator.

Usage:
    python generate.py                        # defaults from config.py
    python generate.py --orders 200 --zones 3 --output-format both

Run `python generate.py --help` for full option reference.
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Allow running from the generator/ directory directly
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

import config
from feeds.order_feed import generate_order_events
from feeds.restaurant_feed import (
    init_restaurant_metadata,
    generate_kitchen_events,
    generate_capacity_signals,
    get_restaurant_zone,
)

# AVRO support (optional — falls back gracefully if fastavro not installed)
try:
    import fastavro
    AVRO_AVAILABLE = True
except ImportError:
    AVRO_AVAILABLE = False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate synthetic food-delivery streaming events."
    )
    p.add_argument("--orders",                  type=int,   default=config.NUM_RESTAURANTS * 5,
                   help="Total orders to simulate (default: restaurants × 5)")
    p.add_argument("--restaurants",             type=int,   default=config.NUM_RESTAURANTS)
    p.add_argument("--couriers",                type=int,   default=config.NUM_COURIERS)
    p.add_argument("--customers",               type=int,   default=config.NUM_CUSTOMERS)
    p.add_argument("--zones",                   type=int,   default=config.NUM_ZONES,
                   help=f"Number of zones (max {len(config.DEFAULT_ZONES)})")
    p.add_argument("--duration-minutes",        type=int,   default=config.SIMULATION_DURATION_MINUTES)
    p.add_argument("--start-hour",              type=int,   default=config.SIMULATION_START_HOUR,
                   help="Simulated start hour 0-23 (affects demand multiplier)")
    p.add_argument("--surge-probability",       type=float, default=config.SURGE_PROBABILITY)
    p.add_argument("--cancellation-probability",type=float, default=config.CANCELLATION_PROBABILITY)
    p.add_argument("--promo-probability",       type=float, default=config.PROMO_PROBABILITY)
    p.add_argument("--weekend",                 action="store_true", default=False,
                   help="Apply weekend demand multiplier")
    p.add_argument("--no-anomalies",            action="store_true", default=False,
                   help="Disable edge-case injection (clean data only)")
    p.add_argument("--output-format",           choices=["json", "avro", "both"],
                   default=config.OUTPUT_FORMAT)
    p.add_argument("--output-dir",              type=str,   default=config.OUTPUT_DIR)
    p.add_argument("--seed",                    type=int,   default=None,
                   help="Random seed for reproducibility")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Entity factories
# ---------------------------------------------------------------------------

def make_ids(prefix: str, n: int) -> List[str]:
    return [f"{prefix}_{str(uuid.uuid4())[:8].upper()}" for _ in range(n)]


# ---------------------------------------------------------------------------
# Demand curve helpers
# ---------------------------------------------------------------------------

def demand_multiplier(hour: int, is_weekend: bool) -> float:
    base = config.HOURLY_DEMAND_MULTIPLIER.get(hour % 24, 0.5)
    return base * (config.WEEKEND_DEMAND_MULTIPLIER if is_weekend else 1.0)


def orders_per_minute(total_orders: int, duration_minutes: int,
                      start_hour: int, is_weekend: bool) -> List[int]:
    """
    Distribute total_orders across simulated minutes using the demand curve.
    Returns a list of length duration_minutes where each element is the number
    of new orders to emit in that minute.
    """
    weights = []
    for m in range(duration_minutes):
        hour = (start_hour + m // 60) % 24
        weights.append(demand_multiplier(hour, is_weekend))

    total_weight = sum(weights)
    schedule = []
    assigned  = 0
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            count = total_orders - assigned
        else:
            count = round(total_orders * w / total_weight)
        schedule.append(max(0, count))
        assigned += count
    return schedule


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_json(records: List[Dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(records, f, indent=config.JSON_INDENT, default=str)
    print(f"  [JSON]  {len(records):>5} records → {path}")


def write_avro(records: List[Dict], schema_path: str, out_path: str) -> None:
    if not AVRO_AVAILABLE:
        print("  [AVRO]  skipped — install fastavro: pip install fastavro")
        return
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(schema_path) as f:
        schema = fastavro.parse_schema(json.load(f))
    with open(out_path, "wb") as f:
        fastavro.writer(f, schema, records)
    print(f"  [AVRO]  {len(records):>5} records → {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    inject_anomalies = not args.no_anomalies

    # Override config with CLI values
    config.CANCELLATION_PROBABILITY = args.cancellation_probability
    config.PROMO_PROBABILITY         = args.promo_probability
    config.SURGE_PROBABILITY         = args.surge_probability

    # ----- Entity setup -----
    num_zones      = min(args.zones, len(config.DEFAULT_ZONES))
    zones          = config.DEFAULT_ZONES[:num_zones]
    zone_weights   = [config.ZONE_DEMAND_WEIGHTS.get(z, 1.0) for z in zones]
    # normalise weights
    total_w        = sum(zone_weights)
    zone_weights   = [w / total_w for w in zone_weights]

    restaurants    = make_ids("REST", args.restaurants)
    couriers       = make_ids("COUR", args.couriers)
    customers      = make_ids("CUST", args.customers)
    devices        = {c: f"DEV_{str(uuid.uuid4())[:8].upper()}" for c in customers}

    init_restaurant_metadata(restaurants)
    # Assign fixed zones to restaurants
    for r in restaurants:
        get_restaurant_zone(r, zones, zone_weights)

    # ----- Simulation time -----
    # Use a fixed "simulation epoch" so event_times are meaningful
    sim_start_dt   = datetime(2026, 3, 10, args.start_hour, 0, 0, tzinfo=timezone.utc)
    sim_start_ms   = int(sim_start_dt.timestamp() * 1000)
    sim_duration_ms= args.duration_minutes * 60 * 1000

    schedule       = orders_per_minute(args.orders, args.duration_minutes,
                                       args.start_hour, args.weekend)

    print(f"\n🍕  Food Delivery Stream Generator")
    print(f"    Orders:      {args.orders}")
    print(f"    Restaurants: {args.restaurants}  |  Couriers: {args.couriers}")
    print(f"    Zones:       {zones}")
    print(f"    Duration:    {args.duration_minutes} min from {args.start_hour:02d}:00")
    print(f"    Anomalies:   {'ON' if inject_anomalies else 'OFF'}")
    print(f"    Output:      {args.output_format} → {args.output_dir}/\n")

    order_events:      List[Dict] = []
    restaurant_events: List[Dict] = []

    # ----- Generate events -----
    for minute, n_orders in enumerate(schedule):
        minute_start_ms = sim_start_ms + minute * 60_000

        for _ in range(n_orders):
            # Surge: temporarily boost cancellation and volume
            if random.random() < args.surge_probability:
                config.CANCELLATION_PROBABILITY = min(0.40, args.cancellation_probability * 2.5)
            else:
                config.CANCELLATION_PROBABILITY = args.cancellation_probability

            # --- Order Lifecycle ---
            o_events = generate_order_events(
                sim_start_ms=minute_start_ms,
                restaurants=restaurants,
                couriers=couriers,
                customers=customers,
                devices=devices,
                zones=zones,
                zone_weights=zone_weights,
                inject_anomalies=inject_anomalies,
            )
            order_events.extend(o_events)

            # --- Restaurant kitchen events (for orders that reach PREPARING) ---
            placed_event  = o_events[0]
            accepted_evts = [e for e in o_events if e["event_type"] == "ACCEPTED"]
            if accepted_evts:
                accepted_t   = accepted_evts[0]["event_time"]
                rid          = placed_event["restaurant_id"]
                zone         = placed_event["zone_id"]
                r_events     = generate_kitchen_events(
                    order_id=placed_event["order_id"],
                    restaurant_id=rid,
                    zone_id=zone,
                    order_accepted_time_ms=accepted_t,
                    inject_anomalies=inject_anomalies,
                )
                restaurant_events.extend(r_events)

    # --- Capacity signals (restaurant-level, not order-bound) ---
    for rid in restaurants:
        from feeds.restaurant_feed import _restaurant_meta
        zone = _restaurant_meta[rid].get("zone_id", zones[0])
        caps = generate_capacity_signals(
            restaurant_id=rid,
            zone_id=zone,
            sim_start_ms=sim_start_ms,
            sim_duration_ms=sim_duration_ms,
            num_signals=random.randint(3, 8),
        )
        restaurant_events.extend(caps)

    # ----- Sort by event_time -----
    order_events.sort(key=lambda e: e["event_time"])
    restaurant_events.sort(key=lambda e: e["event_time"])

    # ----- Write outputs -----
    os.makedirs(args.output_dir, exist_ok=True)
    schema_dir = os.path.join(os.path.dirname(__file__), "..", "schemas")

    print("Writing outputs:")

    if args.output_format in ("json", "both"):
        write_json(order_events,
                   os.path.join(args.output_dir, "order_lifecycle_sample.json"))
        write_json(restaurant_events,
                   os.path.join(args.output_dir, "restaurant_events_sample.json"))

    if args.output_format in ("avro", "both"):
        write_avro(order_events,
                   os.path.join(schema_dir, "order_lifecycle.avsc"),
                   os.path.join(args.output_dir, "order_lifecycle_sample.avro"))
        write_avro(restaurant_events,
                   os.path.join(schema_dir, "restaurant_events.avsc"),
                   os.path.join(args.output_dir, "restaurant_events_sample.avro"))

    # ----- Summary stats -----
    cancelled  = sum(1 for e in order_events if e["event_type"] == "CANCELLED")
    anomalies  = sum(1 for e in order_events + restaurant_events if e.get("is_anomaly"))
    sla_breach = sum(1 for e in restaurant_events if e["event_type"] == "SLA_BREACH")

    print(f"\n✅  Done!")
    print(f"    Order events:      {len(order_events)}")
    print(f"    Restaurant events: {len(restaurant_events)}")
    print(f"    Cancellations:     {cancelled}")
    print(f"    SLA breaches:      {sla_breach}")
    print(f"    Anomalous events:  {anomalies}")


if __name__ == "__main__":
    main()
