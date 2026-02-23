# Milestone 1: Implementation Recommendations

## Overview
This document provides specific code changes to close the gaps identified in the M1 assessment. Prioritized by criticality.

---

## 🔴 CRITICAL: Implement AVRO Generation

### Problem
Requirements 1.2 and 1.4 require AVRO events. Currently, only JSON is generated.

### Solution: Create AvroSink Class

**File:** `generator/src/sinks/avro_sink.py` (NEW)

```python
import os
import json
import fastavro

class AvroSink:
    """
    Serializes events to AVRO binary format.
    
    Each call to write_batch() appends events to a binary AVRO data file.
    File is compatible with fastavro.reader() in downstream code.
    """
    
    def __init__(self, base_dir: str, feed_schemas: dict, feed_names: list):
        """
        Initialize AVRO sink.
        
        Args:
            base_dir: Output directory path
            feed_schemas: Dict mapping feed_name -> parsed AVRO schema dict
                         E.g., {"order_events": {...schema dict...}}
            feed_names: List of feed names to generate files for
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        
        self.feed_schemas = feed_schemas
        self.files = {}
        
        # Open binary files for each feed
        for name in feed_names:
            filepath = os.path.join(base_dir, f"{name}.avro")
            self.files[name] = open(filepath, "wb")
    
    def write_batch(self, feed_name: str, events: list):
        """
        Write a batch of events to AVRO file.
        
        Args:
            feed_name: Name of the feed (e.g., "order_events")
            events: List of event dictionaries
        """
        if not events or feed_name not in self.files:
            return
        
        schema = self.feed_schemas.get(feed_name)
        if not schema:
            raise ValueError(f"Schema not found for feed: {feed_name}")
        
        for event in events:
            # Write each event as an AVRO-serialized record
            fastavro.schemaless_writer(
                self.files[feed_name],
                schema,
                event
            )
    
    def close(self):
        """Flush and close all open files."""
        for f in self.files.values():
            f.close()
    
    @staticmethod
    def load_schema_from_file(schema_path: str) -> dict:
        """
        Load AVRO schema from .avsc file.
        
        Args:
            schema_path: Path to .avsc file
            
        Returns:
            Parsed schema as dict
        """
        with open(schema_path, "r") as f:
            return json.load(f)
```

### Update main.py

```python
from config import load_config
from world import WorldState
from feeds.order_feed import OrderFeed
from feeds.courier_feed import CourierFeed
from edge_cases import EdgeCaseInjector
from sinks.jsonl_sink import JsonlSink
from sinks.avro_sink import AvroSink  # NEW IMPORT
from clocks import SimClock
import os

def main():
    cfg = load_config("config.yaml")

    clock = SimClock(cfg)
    world = WorldState(cfg, rng_seed=cfg["seed"])

    order_feed = OrderFeed(cfg)
    courier_feed = CourierFeed(cfg)
    injector = EdgeCaseInjector(cfg, rng_seed=cfg["seed"] + 1)

    # Initialize sinks
    json_sink = JsonlSink(
        base_dir=cfg["simulation"]["emit_to"],
        feed_names=["order_events", "courier_events"]
    )
    
    # NEW: Initialize AVRO sink
    avro_output_dir = cfg["simulation"].get("emit_to_avro", 
                                             os.path.join(cfg["simulation"]["emit_to"], "../avro"))
    avro_schemas = {
        "order_events": AvroSink.load_schema_from_file("../../avro_schema/order_events_v1.avsc"),
        "courier_events": AvroSink.load_schema_from_file("../../avro_schema/courier_events_v1.avsc")
    }
    avro_sink = AvroSink(
        base_dir=avro_output_dir,
        feed_schemas=avro_schemas,
        feed_names=["order_events", "courier_events"]
    )

    # main loop
    while clock.running():
        now_ms = clock.now_ms()

        # Step feeds (they mutate world + emit events)
        order_events = order_feed.step(world, now_ms)
        courier_events = courier_feed.step(world, now_ms)

        # Inject edge cases (late/out-of-order/duplicates/etc.)
        order_events = injector.apply_to_orders(order_events, world, now_ms)
        courier_events = injector.apply_to_couriers(courier_events, world, now_ms)

        # Write events to both JSON and AVRO
        json_sink.write_batch("order_events", order_events)
        json_sink.write_batch("courier_events", courier_events)
        
        avro_sink.write_batch("order_events", order_events)  # NEW
        avro_sink.write_batch("courier_events", courier_events)  # NEW

        clock.tick()

    json_sink.close()
    avro_sink.close()  # NEW

if __name__ == "__main__":
    main()
```

### Update config.yaml

```yaml
simulation:
  start_ts_ms: 1730000000000
  tick_ms: 1000
  duration_s: 300
  emit_to: "sample_data/json"
  emit_to_avro: "sample_data/avro"  # NEW: AVRO output path
```

### Add to requirements.txt (NEW)

```
fastavro==1.8.0
pyyaml==6.0
```

### Test

```bash
cd generator
pip install -r requirements.txt
python src/main.py
ls -la sample_data/avro/
# Should show: order_events.avro, courier_events.avro
```

---

## 🟡 MEDIUM: Wire Edge Case Flags

### Issue 1: Missing Steps Not Implemented

**Problem:** `missing_step_probability` config flag exists but is never used.

**Location:** `generator/src/feeds/order_feed.py`

**Fix:**

```python
def _maybe_advance_order(self, world: WorldState, order: Order, now_ms: int) -> List[Dict]:
    out = []
    s = order.state

    if s in ("DELIVERED", "REFUNDED"):
        return out

    # Define state progression
    progression = {
        "CREATED": "ASSIGNED",
        "ASSIGNED": "ACCEPTED",
        "ACCEPTED": "PREPARING",
        "PREPARING": "READY",
        "READY": "PICKED_UP",
        "PICKED_UP": "DELIVERED"
    }

    # Check for missing step (skip a state)
    missing_step_prob = self.cfg["edge_cases"].get("missing_step_probability", 0)
    if s in progression and world.rng.random() < missing_step_prob:
        # Skip current state, jump to next
        if progression[s] in progression:
            next_state = progression[progression[s]]
            order.state = next_state
            order.state_ts_ms[next_state] = now_ms
            out.append(self._emit(now_ms, order, next_state))
            return out

    # Normal progression (existing code)
    if s == "CREATED" and world.rng.random() < 0.6:
        courier_id = self._assign_courier(world, order.zone_id)
        if courier_id:
            order.courier_id = courier_id
            order.state = "ASSIGNED"
            order.state_ts_ms["ASSIGNED"] = now_ms
            out.append(self._emit(now_ms, order, "ASSIGNED"))

    # ... rest of existing transitions ...
    
    return out
```

---

### Issue 2: Impossible Durations Not Implemented

**Problem:** `impossible_duration_probability` flag exists but is never used.

**Fix:**

```python
def _maybe_advance_order(self, world: WorldState, order: Order, now_ms: int) -> List[Dict]:
    out = []
    s = order.state

    # ... existing code ...

    # Check for impossible duration (emit events out of order)
    impossible_prob = self.cfg["edge_cases"].get("impossible_duration_probability", 0)
    if world.rng.random() < impossible_prob and s in ("READY", "PICKED_UP"):
        # Emit DELIVERED before PICKED_UP
        # Or emit READY before ACCEPTED
        impossible_state = "DELIVERED" if s == "READY" else "READY"
        
        if impossible_state not in order.state_ts_ms:
            # Emit with earlier timestamp to simulate out-of-order
            impossible_ts = now_ms - world.rng.randint(100, 5000)  # earlier timestamp
            impossible_event = self._emit(impossible_ts, order, impossible_state)
            out.append(impossible_event)
            # Do NOT update order.state (keep current state)
            return out

    # ... rest of logic ...
```

---

### Issue 3: Courier Offline Mid-Delivery

**Problem:** `courier_offline_mid_delivery_probability` flag exists but not fully used.

**Location:** `generator/src/feeds/courier_feed.py`

**Fix:**

```python
def step(self, world: WorldState, now_ms: int) -> List[Dict]:
    events = []
    
    for c in world.couriers.values():
        # Check for offline mid-delivery (critical edge case)
        if (c.status == "ASSIGNED" and c.active_order_id is not None 
            and world.rng.random() < self.cfg["edge_cases"].get("courier_offline_mid_delivery_probability", 0)):
            
            # Courier goes offline while assigned to order
            c.status = "OFFLINE"
            events.append(self._emit(now_ms, c, order_id=c.active_order_id))
            continue  # Skip other status checks for this tick
        
        # Original logic
        if c.status == "OFFLINE" and world.rng.random() < 0.02:
            c.status = "ONLINE"
            events.append(self._emit(now_ms, c, order_id=None))

        elif c.status == "ONLINE" and world.rng.random() < 0.01:
            c.status = "OFFLINE"
            events.append(self._emit(now_ms, c, order_id=c.active_order_id))

        if c.status == "ONLINE" and c.active_order_id is None and world.rng.random() < 0.05:
            c.status = "IDLE"
            events.append(self._emit(now_ms, c, order_id=None))

        if c.status == "IDLE" and world.rng.random() < 0.05:
            c.status = "ONLINE"
            events.append(self._emit(now_ms, c, order_id=None))

    return events
```

---

## 🟢 OPTIONAL: Apply Time-of-Day Variation

### Problem
`orders_this_tick()` ignores lunch/dinner peak and weekday/weekend multipliers.

**Location:** `generator/src/distributions.py`

**Current Code:**
```python
def orders_this_tick(cfg, now_ms, rng):
    base = cfg["demand"]["base_orders_per_min"]
    tick_ms = cfg["simulation"]["tick_ms"]
    per_tick = base * (tick_ms / 60000.0)
    return rng.poisson(per_tick) if hasattr(rng, "poisson") else int(rng.random() < per_tick)
```

**Enhanced Code:**

```python
from datetime import datetime, timezone

def orders_this_tick(cfg, now_ms, rng):
    """
    Generate number of orders for this tick, applying realistic multipliers:
    - Lunch peak (12-14h): 1.6x
    - Dinner peak (19-21h): 1.8x
    - Weekday/weekend variation
    - Surge periods
    """
    base = cfg["demand"]["base_orders_per_min"]
    
    # Apply time-of-day multiplier
    multiplier = get_time_multiplier(cfg, now_ms)
    
    tick_ms = cfg["simulation"]["tick_ms"]
    per_tick = base * multiplier * (tick_ms / 60000.0)
    
    # Use Poisson if available, otherwise simpler approximation
    if hasattr(rng, "poisson"):
        return int(rng.poisson(per_tick))
    else:
        return 1 if rng.random() < per_tick else 0


def get_time_multiplier(cfg, now_ms: int) -> float:
    """
    Calculate demand multiplier based on time of day/week.
    
    Applies:
    - Lunch peak (12-14h): 1.6x
    - Dinner peak (19-21h): 1.8x
    - Weekday/weekend: 1.0x / 1.2x
    - Surge period: 2.0x
    """
    dt = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
    hour = dt.hour
    weekday = dt.weekday()  # 0=Mon, 6=Sun
    
    multiplier = 1.0
    
    # Apply day-of-week multiplier
    if weekday < 5:  # Mon-Fri
        multiplier *= cfg["demand"].get("weekday_multiplier", 1.0)
    else:  # Sat-Sun
        multiplier *= cfg["demand"].get("weekend_multiplier", 1.0)
    
    # Apply lunch peak
    lunch_cfg = cfg["demand"].get("lunch_peak", {})
    if lunch_cfg.get("start_hour", 12) <= hour < lunch_cfg.get("end_hour", 14):
        multiplier *= lunch_cfg.get("multiplier", 1.0)
    
    # Apply dinner peak
    dinner_cfg = cfg["demand"].get("dinner_peak", {})
    if dinner_cfg.get("start_hour", 19) <= hour < dinner_cfg.get("end_hour", 21):
        multiplier *= dinner_cfg.get("multiplier", 1.0)
    
    # Apply surge multiplier
    surge_cfg = cfg["demand"].get("surge", {})
    if surge_cfg.get("enabled", False):
        start_min = surge_cfg.get("start_minute", 0)
        end_min = surge_cfg.get("end_minute", 0)
        
        # Compute minutes since simulation start
        sim_start_ms = cfg["simulation"].get("start_ts_ms", 0)
        minutes_elapsed = (now_ms - sim_start_ms) / (60 * 1000)
        
        if start_min <= minutes_elapsed < end_min:
            multiplier *= surge_cfg.get("multiplier", 1.0)
    
    return multiplier
```

---

## 🟢 OPTIONAL: Apply Zone-Level Demand Skew

### Problem
`choose_zone_weighted()` uses uniform selection despite `zone_skew_alpha` config.

**Location:** `generator/src/distributions.py`

**Current Code:**
```python
def choose_zone_weighted(cfg, world, rng):
    return rng.choice(world.zones)  # uniform
```

**Enhanced Code:**

```python
import numpy as np

def choose_zone_weighted(cfg, world, rng):
    """
    Select a zone with skewed probability.
    
    Uses Dirichlet distribution to create realistic demand concentration
    in certain zones (e.g., downtown more than suburbs).
    """
    alpha = cfg["demand"].get("zone_skew_alpha", 1.3)
    
    # Generate zone weights using Dirichlet distribution
    # Higher alpha = more uniform; lower alpha = more skewed
    weights = np.random.dirichlet([alpha] * len(world.zones))
    
    # Normalize and select
    return rng.choices(world.zones, weights=weights, k=1)[0]
```

**Update imports in main.py:**
```python
import numpy as np
```

---

## Testing Checklist

After implementing fixes:

- [ ] AVRO sink compiles and avro_sink.py has no import errors
- [ ] `main.py` runs without errors
- [ ] AVRO files generated in `sample_data/avro/`
- [ ] AVRO files are non-empty (> 1KB)
- [ ] Read AVRO files with fastavro to validate schema
- [ ] Edge case flags now appear in generated events
- [ ] Time-of-day variation produces higher order counts during peaks
- [ ] Zone selection shows skewed distribution in output statistics

---

## Validation Script

**File:** `generator/validate.py` (NEW)

```python
#!/usr/bin/env python3
import json
import fastavro
import sys
from collections import defaultdict

def validate_json_events(filepath):
    """Validate JSON JSONL events."""
    print(f"\n📄 Validating {filepath}...")
    count = 0
    with open(filepath, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                assert "event_id" in event
                assert "event_ts_ms" in event
                count += 1
            except Exception as e:
                print(f"❌ Error on line {count+1}: {e}")
                return False
    print(f"✅ {count} valid events in {filepath}")
    return True

def validate_avro_events(filepath, schema_path):
    """Validate AVRO binary events."""
    print(f"\n🔷 Validating {filepath} with schema {schema_path}...")
    
    with open(schema_path, "r") as f:
        schema = json.load(f)
    
    count = 0
    try:
        with open(filepath, "rb") as f:
            reader = fastavro.reader(f)
            for event in reader:
                assert "event_id" in event
                assert "event_ts_ms" in event
                count += 1
    except Exception as e:
        print(f"❌ Error reading AVRO: {e}")
        return False
    
    print(f"✅ {count} valid events in {filepath}")
    return True

if __name__ == "__main__":
    # Validate JSON
    json_ok = (
        validate_json_events("generator/sample_data/json/order_events.jsonl") and
        validate_json_events("generator/sample_data/json/courier_events.jsonl")
    )
    
    # Validate AVRO
    avro_ok = (
        validate_avro_events("generator/sample_data/avro/order_events.avro",
                            "avro_schema/order_events_v1.avsc") and
        validate_avro_events("generator/sample_data/avro/courier_events.avro",
                            "avro_schema/courier_events_v1.avsc")
    )
    
    if json_ok and avro_ok:
        print("\n✅ All validations passed!")
        sys.exit(0)
    else:
        print("\n❌ Some validations failed")
        sys.exit(1)
```

**Run:**
```bash
python validate.py
```

---

## Priority Implementation Order

1. **Critical (Day 1):**
   - [ ] Implement AvroSink class
   - [ ] Update main.py to use AvroSink
   - [ ] Update config.yaml
   - [ ] Add fastavro to requirements.txt
   - [ ] Test: `python src/main.py && ls sample_data/avro/`

2. **High (Day 2):**
   - [ ] Wire missing steps edge case
   - [ ] Wire impossible durations edge case
   - [ ] Wire courier offline mid-delivery edge case
   - [ ] Run validation script

3. **Medium (Day 3, if time permits):**
   - [ ] Apply time-of-day variation
   - [ ] Apply zone-level skew
   - [ ] Update documentation with examples

4. **Low (After M2 checkpoint):**
   - [ ] Add test suite
   - [ ] Add visualization/metrics extraction
   - [ ] Performance profiling

---

## Questions?

- **AVRO format:** Using schemaless writer (one record per write). If you need Avro container format with metadata, use `fastavro.writer()` instead.
- **Edge case tuning:** Start with default probabilities in config.yaml. Increase if M2 tests need more edge cases.
- **Backward compatibility:** All changes are backward compatible; existing JSON output unchanged.

---

**Document:** Implementation Recommendations  
**Created:** 23 February 2026  
**Status:** Ready for implementation
