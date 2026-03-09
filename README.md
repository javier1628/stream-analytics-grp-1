# Milestone 1: Food Delivery Stream Analytics

## Project Overview
This project simulates a real-time food delivery ecosystem to enable stream analytics on order lifecycles and restaurant operations.

---

## Feed Justification & Analytics

### 1. Order Lifecycle Feed (`order_lifecycle`)
- **Justification:** Captures the end-to-end journey of a customer order (PLACED → ACCEPTED → PREPARING → PICKED_UP → DELIVERED/CANCELLED). Essential for tracking customer experience and logistics efficiency.
- **Analytics enabled:** 
  - **Delivery Time Distribution:** Real-time monitoring of average delivery times.
  - **Cancellation Rates:** Identifying spikes in cancellations by zone or time.
  - **Zone Surge Detection:** Detecting high-demand areas to dynamically adjust courier allocation.

### 2. Restaurant Events Feed (`restaurant_events`)
- **Justification:** Focuses on the "black box" of the kitchen (PREP_STARTED → PREP_COMPLETE) and restaurant-level signals (SLA_BREACH, CAPACITY_CHANGE). Essential for operational efficiency and partner management.
- **Analytics enabled:**
  - **Prep SLA Monitoring:** Identifying restaurants consistently breaching preparation time agreements.
  - **Kitchen Throughput:** Measuring real-time capacity and bottlenecks.
  - **Anomaly Detection:** Identifying impossible preparation durations or skipped operational steps.

---

## Event-Time & Late Data Handling

To support robust stream processing (e.g., in Apache Flink or Spark Streaming), every event includes:
- **`event_time`**: The UTC epoch milliseconds when the event *actually occurred* in the simulation. This is the primary field for **watermarking** and windowing.
- **`ingestion_time`**: The time the event was emitted by the generator.

### Handling Watermarks & Late Data:
- **Out-of-Order Events:** The generator injects ~5% out-of-order events (where `event_time` < previous event's `event_time`). This tests the pipeline's ability to handle late-arriving data using watermarks.
- **Duplicates:** ~2% of events are duplicated to test idempotent processing and deduplication logic.
- **Watermarks:** Analytics pipelines should use `event_time` with a reasonable delay (e.g., 5-10 seconds) to allow for the late data injected by this generator.

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
1. **Network Latency:** Simulated via out-of-order `event_time` vs `ingestion_time`.
2. **Zone-based Demand:** Demand is skewed towards `ZONE_CENTRO` by default.
3. **Courier Availability:** Simulated pool of couriers that can be temporarily overloaded during surges.

### Planned Analytics:
- **SLA Breach Detection:** Real-time alerts when a restaurant exceeds its preparation time.
- **Delivery Time Prediction:** Using current prep times and zone congestion to estimate delivery.
- **Anomaly Detection:** Identifying fraudulent or impossible event sequences (e.g., delivered before picked up).
- **Zone Performance:** Comparative analysis of cancellation rates and delivery times across different geographic zones.
