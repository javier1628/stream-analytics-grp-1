# Milestone 1: Food Delivery Stream Analytics

## Project Overview
Table Streaming Project Goal: Set up a real time food delivery system to do stream analytics on the order life cycle and on the restaurant operations.

**Team Structure:**
- **Lead Data Engineer:** [Name]
- **Stream Processing Specialist:** [Name]
- **Analytics Engineer:** [Name]

---

## Feed Justification & Analytics

### 1. Order Lifecycle Feed (`order_lifecycle`)
- **Status Justification:** This status reflects the entire workflow of a customer order from PLACED → ACCEPTED → PREPARING → PICKED_UP to DELIVERED/CANCELLED. It is of high importance for the customer satisfaction and the efficiency of the logistics processes.
- **Analytics enabled:**
- **Delivery Time Distribution:** Real-time monitoring of average delivery times.
- **Cancellation Rates:** Identifying spikes in cancellations by zone or time.
- **Zone Surge Detection:** Detecting high-demand areas to dynamically adjust courier allocation.

### 2. Restaurant Events Feed (`restaurant_events`)
- **Justification:** The focus should be on the “black box” of the kitchen (PREP_STARTED → PREP_COMPLETE) and on the high level signals in the restaurant (SLA_BREACH, CAPACITY_CHANGE).
- **Analytics enabled:**
- **Prep SLA Monitoring:** Identifying restaurants consistently breaching preparation time agreements.
- **Kitchen Throughput:** Measuring real-time capacity and bottlenecks.
- **Anomaly Detection:** Identifying impossible preparation durations or skipped operational steps.

---

## Event-Time & Late Data Handling

Watermarks and Event Time for Robust Stream Processing It is assumed that for real-time data processing every event in a stream must have a watermark and an event time. In the following we give a short overview which information must be contained in each event.
- **`event_time`**: The UTC epoch milliseconds when the event *actually occurred* in the simulation. The main field to use for watermarking and windowing.
- **`ingestion_time`**: The time the event was emitted by the generator.

### Handling Watermarks & Late Data:
- **Out-of-Order Events:** We are generating around ~5% out-of-order events (where `event_time` < previous event's `event_time`). This is to test the use of watermarks in handling late events in the stream.
- **Duplicates:** About 2% of the events are duplicated in order to verify the idempotence of the processing and to check the deduplication.
- **Watermarks:** We should use the event_time with a small offset, e.g. 5-10 seconds, in order to be able to handle the late data injected by this source.

---

## Repository Structure

```
/
├── generate.py           # Main entry point for event generation
├── config.py             # Simulation parameters (demand, zones, anomalies)
├── order_feed.py         # Logic for Order Lifecycle events
├── restaurant_feed.py    # Logic for Restaurant/Kitchen events
├── requirements.txt      # Project dependencies (fastavro)
├── schemas/              # AVRO Schema definitions
│   ├── order_lifecycle.avsc
│   └── restaurant_events.avsc
├── sample_data/          # Milestone 1 sample outputs
│   ├── order_lifecycle_sample.json
│   ├── order_lifecycle_sample.avro
│   ├── restaurant_events_sample.json
│   └── restaurant_events_sample.avro
└── README.md             # This documentation
```

---

## How to Run

### Setup
```bash
pip install -r requirements.txt
```

### Generate Milestone 1 Samples
To generate the samples included in `sample_data/`:
```bash
# Generate JSON samples
python generate.py --duration 2 --orders-per-minute 20 --output-dir sample_data --format json

# Generate AVRO samples and verify them
python generate.py --duration 2 --orders-per-minute 20 --output-dir sample_data --format avro --verify
```

### Custom Simulation
```bash
python generate.py --orders 500 --duration 60 --format both --verify
```

---

## Assumptions & Planned Analytics

### Assumptions:
1. ** Network Latency:** Simulated via out-of-order `event_time` vs `ingestion_time`.
2. ** Zone-based Demand:** Demand is skewed towards `ZONE_CENTRO` by default.
Challenge 3: 3D Courier Availability A simulation model of a pool of couriers available to act as 3D courier delivery drivers, with the pool potentially becoming temporarily saturated with drivers during peak surge periods.

### Planned Analytics:
- **SLA Breach Detection:** Will send real time alerts to the restaurant when the SLA for preparation time is breached.
- **Delivery Time Prediction** - Estimate the delivery time based on prep time history and real time zone congestion.
- **Anomaly Detection:** This type of detection uncovers clearly fraudulent or clearly impossible events in the event stream e.g. something being delivered before it being picked up.
- **Zone Performance:** A comparison of cancellation rates and delivery times per zone.
