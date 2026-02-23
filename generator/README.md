# Food Delivery Streaming Generator

This module generates synthetic real-time streaming events representing a food delivery marketplace.

It produces two event streams:

- **`order_events`** — customer demand and lifecycle events  
- **`courier_events`** — courier supply and availability state  

Events are written in:

- JSON (newline-delimited `.jsonl`)
- AVRO (Avro Object Container Files)

The generator is configurable and supports realism and streaming edge cases required for Milestone 1.

---

## Setup Instructions

### 1. Create a Virtual Environment (Recommended)

From inside the `generator/` directory:

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```
2. Install Dependencies
```bash
pip install -r requirements.txt
```
Dependencies include:
```bash
pyyaml — configuration loading

fastavro — AVRO writing
```
numpy (optional) — advanced statistical distributions

Running the Generator

From inside the generator/ directory:
```bash
PYTHONPATH=src python src/main.py
```
On Windows:
```bash
set PYTHONPATH=src
python src/main.py
```
The simulation runs according to parameters defined in config.yaml.

Output Files

Generated files are written to:
```bash
sample_data/json/
sample_data/avro/
```
Example outputs:
```bash
sample_data/json/order_events.jsonl
sample_data/json/courier_events.jsonl

sample_data/avro/order_events_0001.avro
sample_data/avro/courier_events_0001.avro
```
Each AVRO file is a valid Avro container file and can be read using Spark, fastavro, or other AVRO-compatible tools.

Configuration

All simulation behavior is controlled via:
```bash
generator/config.yaml
```
Simulation Settings

start_ts_ms — simulation start timestamp (epoch millis)

tick_ms — simulation step size

duration_s — total run duration

Entity Counts

num_zones

num_restaurants

num_couriers

Demand Controls

base_orders_per_min

Lunch/Dinner peak multipliers

Weekend multiplier

Surge windows

Behavior Controls

Cancellation probability

Failure probability

Refund probability

Edge Case Controls

duplicate_probability

late_event_probability

missing_step_probability

impossible_duration_probability

courier_offline_mid_delivery_probability

All probabilities are configurable and applied per event or per order lifecycle.

Supported Streaming Edge Cases

The generator intentionally produces streaming correctness scenarios:

Late or out-of-order events

Duplicate events (same event_id)

Missing lifecycle steps

Impossible durations

Courier going offline mid-delivery

These are required to demonstrate watermarking, stateful processing, and anomaly detection in Spark Structured Streaming.

Architecture Overview

The generator consists of:

world.py — shared simulation state (zones, restaurants, couriers, orders)

order_feed.py — order lifecycle emitter

courier_feed.py — courier availability emitter

edge_cases.py — streaming anomaly injection layer

jsonl_sink.py — JSON writer

avro_sink.py — AVRO writer

Both feeds share a common world state to ensure consistent identifiers and proper joinability.

Verifying Output

To inspect JSON output:
```bash
head sample_data/json/order_events.jsonl
```
To inspect AVRO output:
```bash
python - <<EOF
from fastavro import reader
with open("sample_data/avro/order_events_0001.avro","rb") as f:
    for r in reader(f):
        print(r)
        break
EOF
```
Design Notes

Event time is stored in event_ts_ms (epoch milliseconds).

Schemas are versioned using schema_version = 1.

Partitioning strategy for Milestone 2:

order_events → partition by order_id

courier_events → partition by courier_id

Troubleshooting

If you encounter:
```bash
ModuleNotFoundError
```
Ensure you are running:
```bash
PYTHONPATH=src python src/main.py
```
If AVRO writing fails:

Verify schema file paths are correct

Ensure fastavro is installed

Ensure output directories exist

### 2. Validator test to check for data correctness

Validate JSONL (default paths)

If you generated JSON to the default locations, you can simply run:
```bash
python validate_output.py
```
Defaults:
```bash
--json-order sample_data/json/order_events.jsonl

--json-courier sample_data/json/courier_events.jsonl
```
Validate JSONL with explicit paths
```bash
python validate_output.py \
  --json-order path/to/order_events.jsonl \
  --json-courier path/to/courier_events.jsonl
```
Validate JSONL + AVRO files
```bash
python validate_output.py \
  --json-order sample_data/json/order_events.jsonl \
  --json-courier sample_data/json/courier_events.jsonl \
  --avro-order sample_data/avro/order_events_0001.avro \
  --avro-courier sample_data/avro/courier_events_0001.avro
  ```
Validate a directory of AVRO files

You may pass a directory instead of a single file. The script will:

Prefer files containing the feed hint in the filename (*order*.avro or *courier*.avro)

Otherwise, read all *.avro files in the directory
```bash
python validate_output.py \
  --avro-order sample_data/avro \
  --avro-courier sample_data/avro
```

Output format

The script prints a report like:
```bash
PASS <check name> - <details>

FAIL <check name> - <details>
```
It may also print a WARNINGS section (e.g., if JSON vs AVRO record counts differ).

At the end:
```bash
Checks: <N> | Failures: <M> | Warnings: <K>
```