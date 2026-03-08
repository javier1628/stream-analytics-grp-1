# Real-Time Food Delivery Stream Analytics

**IE University — Stream Analytics · Spring 2026 · Group Project**

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Team Structure](#team-structure)
3. [Repository Layout](#repository-layout)
4. [Feed Design](#feed-design)
   - [Feed 1 · Order Lifecycle Events](#feed-1--order-lifecycle-events)
   - [Feed 2 · Restaurant Events](#feed-2--restaurant-events)
5. [Why These Two Feeds?](#why-these-two-feeds)
6. [Analytics Roadmap](#analytics-roadmap)
7. [Event-Time & Late Data Strategy](#event-time--late-data-strategy)
8. [Edge Cases & Streaming Correctness](#edge-cases--streaming-correctness)
9. [Running the Generator](#running-the-generator)
10. [Assumptions & Simplifications](#assumptions--simplifications)

---

## Project Overview

This project designs and implements a **real-time analytics pipeline** for a synthetic food delivery
platform (think Uber Eats / Glovo). We ingest two high-volume streaming feeds, process them with
**Spark Structured Streaming**, store curated results in **Azure Blob Storage (Parquet)**, and serve
live insights via a **Streamlit dashboard**.

Milestone 1 focuses on:
- Designing two event feeds with justified schemas
- Implementing a configurable Python event generator
- Producing sample data in both **JSON** and **AVRO** formats

---

## Team Structure

| Name | Role / Focus Area |
|------|-------------------|
| TBD  | Feed generator & schema design |
| TBD  | Spark processing (Milestone 2) |
| TBD  | Azure infrastructure & ingestion |
| TBD  | Dashboard & visualization |
| TBD  | Documentation & testing |

> Update this table with your actual team members before submission.

---

## Repository Layout

```
stream-analytics/
│
├── README.md                        ← This file
│
├── schemas/
│   ├── order_lifecycle.avsc         ← AVRO schema: Order Lifecycle Events
│   └── restaurant_events.avsc       ← AVRO schema: Restaurant Events
│
├── generator/
│   ├── README.md                    ← Generator-specific docs
│   ├── generate.py                  ← Main entry point
│   ├── feeds/
│   │   ├── order_feed.py            ← Order Lifecycle generator
│   │   └── restaurant_feed.py       ← Restaurant Events generator
│   ├── config.py                    ← Configurable parameters
│   └── requirements.txt
│
└── sample_data/
    ├── order_lifecycle_sample.json
    ├── order_lifecycle_sample.avro
    ├── restaurant_events_sample.json
    └── restaurant_events_sample.avro
```

---

## Feed Design

### Feed 1 · Order Lifecycle Events

**Purpose:** Captures every state transition an order goes through, from placement to delivery
(or cancellation). This is the **central transaction log** of the platform.

#### Event States (Finite State Machine)

```
PLACED → ACCEPTED → PREPARING → READY_FOR_PICKUP → PICKED_UP → DELIVERED
                                                              ↘ CANCELLED (any stage)
```

#### Schema Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `string` (UUID) | Unique event identifier (for deduplication) |
| `order_id` | `string` (UUID) | Links all events belonging to the same order |
| `event_type` | `enum` | One of: `PLACED`, `ACCEPTED`, `PREPARING`, `READY_FOR_PICKUP`, `PICKED_UP`, `DELIVERED`, `CANCELLED` |
| `event_time` | `long` (epoch ms) | **Event time** — when the state change actually occurred |
| `ingestion_time` | `long` (epoch ms) | When the event was emitted to the stream (for lag measurement) |
| `customer_id` | `string` | Customer identifier (for fraud/refund heuristics) |
| `restaurant_id` | `string` | Links to restaurant reference data |
| `courier_id` | `string` (nullable) | Assigned after `ACCEPTED`; null before |
| `zone_id` | `string` | Geographic delivery zone (e.g., `ZONE_CENTRO`, `ZONE_NORTH`) |
| `order_value_eur` | `float` | Gross order value in EUR |
| `item_count` | `int` | Number of items in the order |
| `promo_applied` | `boolean` | Whether a promotion was used |
| `cancellation_reason` | `string` (nullable) | Only populated on `CANCELLED` events |
| `device_id` | `string` | Device fingerprint (for fraud detection in Milestone 2) |

#### Design Notes

- `event_time` is the **authoritative timestamp** for all windowing operations.
- `order_id` is the **join key** connecting lifecycle events to restaurant events.
- `zone_id` enables zone-level aggregations (demand/supply balance, anomaly detection).
- `courier_id` being nullable allows the schema to represent pre-assignment states cleanly.

---

### Feed 2 · Restaurant Events

**Purpose:** Captures operational milestones from the restaurant's perspective — order acknowledgement,
kitchen preparation progress, and SLA breaches. This feed enables **prep-time analytics** and
**restaurant performance monitoring**.

#### Event Types

```
ORDER_RECEIVED → PREP_STARTED → PREP_COMPLETE → HANDOFF_TO_COURIER
                              ↘ SLA_BREACH (prep exceeded threshold)
RESTAURANT_BUSY / RESTAURANT_AVAILABLE  (capacity signals)
```

#### Schema Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | `string` (UUID) | Unique event identifier (deduplication) |
| `order_id` | `string` (UUID) | **Join key** — links back to Order Lifecycle feed |
| `restaurant_id` | `string` | Restaurant identifier |
| `event_type` | `enum` | One of: `ORDER_RECEIVED`, `PREP_STARTED`, `PREP_COMPLETE`, `HANDOFF_TO_COURIER`, `SLA_BREACH`, `RESTAURANT_BUSY`, `RESTAURANT_AVAILABLE` |
| `event_time` | `long` (epoch ms) | When the milestone occurred at the restaurant |
| `ingestion_time` | `long` (epoch ms) | Emission timestamp (lag tracking) |
| `zone_id` | `string` | Zone the restaurant belongs to |
| `prep_duration_seconds` | `int` (nullable) | Set on `PREP_COMPLETE`; null otherwise |
| `sla_threshold_seconds` | `int` | Agreed maximum prep time (e.g., 900 = 15 min) |
| `queue_depth` | `int` | Active orders in kitchen at time of event |
| `capacity_pct` | `float` | Estimated kitchen load (0.0–1.0) |
| `cuisine_type` | `enum` | e.g., `PIZZA`, `SUSHI`, `BURGER`, `SALAD` — for segment analytics |
| `is_partner_restaurant` | `boolean` | Priority SLA tier flag |

#### Design Notes

- `prep_duration_seconds` on `PREP_COMPLETE` events allows direct **SLA compliance** calculation
  without expensive stream-to-stream joins.
- `queue_depth` and `capacity_pct` support a **demand-supply health metric** per zone
  (restaurant pressure vs. available couriers, joining with Order Lifecycle).
- `sla_threshold_seconds` is embedded per event to allow threshold to vary by restaurant tier.
- `order_id` is the **foreign key** for joining with Order Lifecycle events in Milestone 2.

---

## Why These Two Feeds?

| Criterion | Order Lifecycle | Restaurant Events |
|-----------|----------------|-------------------|
| **Business coverage** | Customer-facing: what was ordered, when, by whom | Ops-facing: how restaurants perform under load |
| **Analytics enabled** | Delivery time KPIs, cancellation rates, fraud | Prep-time SLA, kitchen overload alerts |
| **Join potential** | Acts as the primary stream | Enriches lifecycle with kitchen context |
| **Windowing suitability** | Tumbling windows (orders/min by zone) | Session windows (restaurant busy periods) |
| **Late data risk** | High — courier GPS can delay `PICKED_UP` | Medium — kitchen events may batch-emit |

Together, these two feeds cover **the full critical path** of a delivery: order placement → kitchen
preparation → pickup → delivery. Every advanced use case in Milestone 2 (SLA monitoring, anomaly
detection, surge prediction) requires data from both feeds.

---

## Analytics Roadmap

### Use Case 1 — Basic (Windowed KPIs)
- Orders placed per 5-minute tumbling window, broken down by `zone_id`
- Cancellation rate per 10-minute hopping window
- Average `order_value_eur` over rolling windows

### Use Case 2 — Intermediate (Stateful)
- **Restaurant SLA monitoring**: per-restaurant `prep_duration_seconds` percentiles (p50/p95)
  computed over session windows aligned to restaurant busy periods
- **Demand–supply health per zone**: join active orders (from Order Lifecycle) with `queue_depth`
  (from Restaurant Events) to produce a zone health score

### Use Case 3 — Advanced (Anomaly / Fraud)
- **Delivery time anomaly detection**: flag orders where end-to-end time exceeds zone-level p95
  baseline (with late data handled via watermarks)
- **Fraud heuristics**: repeated cancellations from same `customer_id` / `device_id` within a
  sliding window

---

## Event-Time & Late Data Strategy

| Concern | Our Approach |
|---------|-------------|
| **Event time field** | `event_time` (epoch ms) on every event — authoritative timestamp |
| **Ingestion lag** | `ingestion_time` recorded separately to measure broker lag |
| **Watermark** | 10-minute watermark on Order Lifecycle; 5-minute on Restaurant Events |
| **Out-of-order events** | Generator intentionally delays ~5% of events by up to 8 minutes |
| **Late arrivals** | Events beyond watermark are flagged and routed to a dead-letter log |

Watermark values are chosen to balance **result completeness** (larger = more correct) against
**latency** (smaller = faster dashboards). 10 minutes is justified by mobile network conditions
causing courier GPS delays; 5 minutes covers typical kitchen tablet connectivity issues.

---

## Edge Cases & Streaming Correctness

The generator deliberately injects the following pathological patterns to stress-test the pipeline:

| Pattern | How Generated | Why It Matters |
|---------|--------------|----------------|
| **Out-of-order events** | 5% of events delayed by 2–8 min random offset | Tests watermark correctness |
| **Duplicate events** | 2% of events re-emitted with same `event_id` | Tests idempotent deduplication |
| **Missing steps** | `DELIVERED` without prior `PICKED_UP` (~1%) | Tests incomplete state machines |
| **Impossible durations** | `prep_duration_seconds` > 3600 (~0.5%) | Triggers anomaly detection |
| **Courier goes offline** | `courier_id` appears in `PICKED_UP` but not `DELIVERED` | Simulates drop-offs |
| **SLA breach without prep complete** | `SLA_BREACH` emitted, `PREP_COMPLETE` never follows | Tests partial session windows |

---

## Running the Generator

```bash
# Install dependencies
pip install -r generator/requirements.txt

# Run with defaults (500 orders, 20 restaurants, 2 zones)
python generator/generate.py

# Custom configuration
python generator/generate.py \
  --orders 2000 \
  --restaurants 50 \
  --zones 5 \
  --duration-minutes 60 \
  --surge-probability 0.15 \
  --cancellation-probability 0.08 \
  --output-format both        # json | avro | both
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--orders` | 500 | Total orders to simulate |
| `--restaurants` | 20 | Number of distinct restaurants |
| `--zones` | 3 | Geographic zones |
| `--duration-minutes` | 60 | Simulated time window |
| `--surge-probability` | 0.10 | Probability of a demand surge starting |
| `--cancellation-probability` | 0.07 | Baseline order cancellation rate |
| `--lunch-peak` | True | Enable lunch (12:00–14:00) traffic amplification |
| `--dinner-peak` | True | Enable dinner (19:00–22:00) traffic amplification |
| `--output-format` | `json` | Output format: `json`, `avro`, or `both` |
| `--inject-anomalies` | True | Inject out-of-order, duplicates, missing steps |

---

## Assumptions & Simplifications

- **Geography**: Zones are abstract labels (`ZONE_A`, `ZONE_B`, …) with no real GPS coordinates.
  Courier GPS simulation is deferred to a potential Courier feed in Milestone 2.
- **Time simulation**: The generator operates in **accelerated simulated time** — one real second
  represents one simulated minute — so a full rush-hour scenario runs in ~2 minutes of wall time.
- **Restaurant reference data**: Static metadata (name, cuisine type, SLA tier) is generated once
  at startup and embedded in events; a proper reference table lookup is planned for Milestone 2.
- **AVRO versioning**: Schemas are at version `1.0`. Nullable fields use AVRO union `["null", type]`
  to preserve forward/backward compatibility for future schema evolution.
- **No auth/encryption**: The generator writes plain files locally. Azure Event Hubs connection
  strings and credentials will be handled in Milestone 2 via environment variables / Key Vault.
