# Feed Generator

Synthetic event generator for the Real-Time Food Delivery Stream Analytics project.  
Produces **Order Lifecycle** and **Restaurant Events** in JSON and AVRO format.

---

## Quick Start

```bash
# Install dependency
pip install -r requirements.txt

# Run with defaults (100 orders, 20 restaurants, 3 zones, 60-minute lunch window)
python generate.py

# Custom run
python generate.py \
  --orders 500 \
  --restaurants 30 \
  --couriers 60 \
  --zones 4 \
  --start-hour 19 \
  --duration-minutes 90 \
  --weekend \
  --output-format both \
  --output-dir ../sample_data
```

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--orders` | 100 | Total orders to simulate |
| `--restaurants` | 20 | Number of distinct restaurants |
| `--couriers` | 40 | Number of active couriers |
| `--customers` | 500 | Customer pool size |
| `--zones` | 3 | Number of geographic zones (max 5) |
| `--duration-minutes` | 60 | Simulated time window length |
| `--start-hour` | 12 | Start hour 0–23 (drives demand curve) |
| `--surge-probability` | 0.10 | Probability of a demand surge event |
| `--cancellation-probability` | 0.07 | Base order cancellation rate |
| `--promo-probability` | 0.20 | Fraction of orders with a promo |
| `--weekend` | False | Apply 1.25× weekend multiplier |
| `--no-anomalies` | False | Disable edge-case injection |
| `--output-format` | `both` | `json` \| `avro` \| `both` |
| `--output-dir` | `sample_data` | Output directory |
| `--seed` | None | Random seed for reproducibility |

---

## Demand Realism

### Hourly demand curve
Orders are distributed across the simulation window using a pre-defined
hourly multiplier (see `config.HOURLY_DEMAND_MULTIPLIER`). Running with
`--start-hour 12` generates a **lunch peak** pattern; `--start-hour 19`
produces a **dinner peak**.

### Zone-level skew
`ZONE_CENTRO` receives 40% of demand by default; outer zones share the remainder.
Weights are defined in `config.ZONE_DEMAND_WEIGHTS` and are fully configurable.

### Weekend multiplier
Pass `--weekend` to apply a 1.25× uplift across all hours.

### Demand surges
With probability `--surge-probability`, a surge begins in any given simulation
minute, temporarily doubling the cancellation rate to simulate restaurant overload.

---

## Edge-Case Injection

The following anomalies are injected by default (`--no-anomalies` disables all):

| Anomaly | Rate | Purpose |
|---------|------|---------|
| Out-of-order events | 5% | Tests watermark / late-data handling |
| Duplicate events | 2% | Tests idempotent deduplication logic |
| Missing PICKED_UP step | 1% | Tests incomplete FSM state handling |
| Impossible prep duration (>3600 s) | 0.5% | Triggers anomaly detection |
| Courier goes offline mid-delivery | 2% | Ends order with CANCELLED / COURIER_TIMEOUT |
| SLA breach without PREP_COMPLETE | varies | Tests partial session window handling |

All injected anomalous events carry `"is_anomaly": true` for easy filtering
during pipeline testing.

---

## Project Layout

```
generator/
├── generate.py          ← Entry point
├── config.py            ← All tunable parameters
├── requirements.txt
├── README.md            ← This file
└── feeds/
    ├── order_feed.py    ← Order Lifecycle event logic
    └── restaurant_feed.py  ← Restaurant Events logic
```

---

## Output Format Notes

**JSON**: Array of event objects. One file per feed.  
**AVRO**: Binary Avro container file. Schemas are read from `../schemas/`.  
Both formats follow the same field names and types as defined in the AVRO schemas.

Timestamps (`event_time`, `ingestion_time`) are epoch milliseconds (int64).

---

## Reproducibility

Pass `--seed <int>` for fully deterministic output:

```bash
python generate.py --orders 200 --seed 42
```
