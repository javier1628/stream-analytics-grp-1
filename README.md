# stream-analytics-grp-1

## Project overview

### 1. Overview

This project designs and implements two real-time streaming data feeds representing the core operational dynamics of a food delivery marketplace. The selected feeds model:

Demand → customer orders and lifecycle events (order_events)

Supply → courier availability and assignment state (courier_events)

Together, these feeds enable real-time analytics such as throughput monitoring, supply–demand health assessment, operational anomaly detection, and session-based courier activity tracking.

All events are generated synthetically using a configurable Python-based generator. Events are produced in both JSON and AVRO formats, with schemas defined using versioned AVRO specifications.

The system is designed explicitly for event-time stream processing using Spark Structured Streaming in Milestone 2.

### 2. Selected Feeds and Justification
2.1 Feed A – order_events (Demand + Order Lifecycle)

This feed represents customer demand and the operational lifecycle of food delivery orders.

It captures state transitions from order creation through preparation, pickup, delivery, cancellation, failure, or refund.

Why this feed is essential

Orders are the primary unit of marketplace demand.

Lifecycle milestones enable delivery time, preparation time, and anomaly detection analytics.

It supports windowed throughput monitoring and supply–demand health metrics when joined with courier data.

Analytics Enabled

Basic (Windowed KPIs)

Orders created per 10-minute window (by zone / restaurant)

Intermediate (Stateful / Join-based)

Demand–supply health metric per zone (joined with courier feed)

Advanced (Anomaly Detection)

Delivery time spikes per zone

Impossible duration detection (e.g., READY before ACCEPTED)

2.2 Feed B – courier_events (Supply + Availability State)

This feed represents the operational supply side of the marketplace.

It captures courier availability transitions and assignment state changes.

Why this feed is essential

Supply visibility is required to compute marketplace balance.

Enables session-based courier analytics (ONLINE → OFFLINE).

Required to compute demand–supply health and courier utilization.

Analytics Enabled

Basic

Active couriers per 10-minute window by zone

Intermediate

Courier session windows (ONLINE → OFFLINE)

Demand–supply health per zone (orders vs available couriers)

Advanced

Detection of courier offline mid-delivery

Correlation between courier availability drops and delivery delays

### 3. Topic and Partitioning Strategy (For Milestone 2)

Although Milestone 1 focuses on feed generation, the design anticipates ingestion into Azure Event Hubs in Milestone 2.

Topics

order_events

courier_events

Partitioning Strategy

order_events partition key: order_id

courier_events partition key: courier_id

Rationale

Keeps lifecycle events for a given entity in the same partition.

Reduces cross-partition reordering for stateful processing.

Supports session-window computation in Spark.

### 4. Schema Design Principles

Both feeds follow the same structural design philosophy:

Event-Time First

event_ts_ms (epoch milliseconds) represents when the real-world event occurred.

This field is used for Spark windowing and watermarking.

Uniqueness and Deduplication

event_id is globally unique.

Duplicate events reuse the same event_id to support idempotent processing.

Versioning

schema_version is included in all records.

Initial version: 1.

Future backward-compatible changes will add optional fields.

Join Identifiers

Identifiers included to support stream joins and enrichment:

order_id

courier_id

restaurant_id

zone_id

customer_id

One Schema per Feed

Each feed uses:

A single AVRO schema

An event_type (orders) or status (couriers) enum to distinguish event semantics

### 5. Feed Schemas (Logical Design)
5.1 order_events Schema (v1)
Field	Type	Required	Description
schema_version	int	Yes	Schema version identifier
event_id	string	Yes	Globally unique event identifier
event_ts_ms	long	Yes	Event-time in epoch milliseconds
order_id	string	Yes	Unique order identifier
event_type	enum	Yes	Order lifecycle state
zone_id	string	Yes	Order geography
restaurant_id	string	Yes	Restaurant fulfilling the order
customer_id	string	Yes	Customer placing the order
courier_id	union(null,string)	Optional	Assigned courier (present after ASSIGNED)
order_value_cents	union(null,int)	Optional	Order monetary value
currency	union(null,string)	Optional	Currency code
cancel_reason	union(null,string)	Optional	Present for CANCELLED
fail_reason	union(null,string)	Optional	Present for FAILED
event_type Enum Values

CREATED

ASSIGNED

ACCEPTED

PREPARING

READY

PICKED_UP

DELIVERED

CANCELLED

FAILED

REFUNDED

Duration Derivation

Durations are computed analytically:

Preparation time = ACCEPTED → READY

Delivery time = PICKED_UP → DELIVERED

Total lifecycle = CREATED → DELIVERED

5.2 courier_events Schema (v1)
Field	Type	Required	Description
schema_version	int	Yes	Schema version identifier
event_id	string	Yes	Globally unique event identifier
event_ts_ms	long	Yes	Event-time
courier_id	string	Yes	Courier identifier
zone_id	string	Yes	Courier zone at event time
status	enum	Yes	Courier operational state
order_id	union(null,string)	Optional	Associated order if applicable
status Enum Values

ONLINE

OFFLINE

IDLE

ASSIGNED

This minimal state model supports:

Courier session windows (ONLINE → OFFLINE)

Assignment visibility

Demand–supply health metrics

### 6. Event-Time Processing and Late Data Handling
Event-Time vs Processing-Time

event_ts_ms represents when the operational action occurred.
Processing-time (ingestion time) may differ due to buffering, retries, batching, or network variability.

This design explicitly supports event-time processing with watermarks in Spark Structured Streaming.

Lateness Model (Generator Behavior)

To demonstrate watermark handling:

90–95% of events: 0–10 seconds late

4–9% of events: 10–120 seconds late

0.5–1% of events: 2–10 minutes late

In Milestone 2, Spark will apply a watermark (e.g., 10 minutes) to correctly handle late data while bounding state growth.

### 7. Realism and Configurability

The synthetic generator models realistic marketplace behavior:

Demand Realism

Lunch and dinner peak demand

Weekday vs weekend variation

Zone-level demand skew

Configurable cancellation probability

Configurable demand surge periods

Supply Realism

Couriers transition between ONLINE and OFFLINE

More couriers available during peak demand

Zone-based courier distribution

Configurable Parameters

Number of restaurants

Number of couriers

Number of zones

Base demand rate

Surge multiplier

Cancellation probability

Duplicate probability

Late event probability

Edge-case toggles

### 8. Streaming Correctness Edge Cases

The generator intentionally produces edge cases to demonstrate streaming robustness:

Out-of-order events (late arrivals)

Duplicate events (same event_id)

Missing lifecycle steps (e.g., DELIVERED without PICKED_UP)

Impossible durations (e.g., READY before ACCEPTED)

Courier offline mid-delivery

These cases validate watermark logic, deduplication, and anomaly detection in Milestone 2.

### 9. Planned Metrics for Milestone 2
Basic Use Cases

Orders per 10-minute tumbling window

Active couriers per 10-minute window

Intermediate Use Cases

Courier active sessions (session windows)

Demand–supply health per zone

Advanced Use Cases

Delivery-time spike anomaly detection (with late data handling)

Impossible duration detection

### 10. Assumptions

Each restaurant belongs to exactly one zone.

A courier operates in one zone at a time.

No courier reassignment is modeled (single courier per order).

Refunds occur only after cancellation or failure.

One schema per feed with event-type enum design.

### 11. Conclusion

The selected order_events and courier_events feeds provide a minimal yet complete representation of marketplace demand and supply dynamics.

The schema design prioritizes:

Event-time correctness

Joinability across feeds

Statefulness for session analytics

Robust handling of late and duplicate events

This foundation enables scalable stream processing, windowed analytics, and real-time dashboard visualization in subsequent milestones.

## Team structure
Ee Herng - Feed Architect
Javier - Schema Architect
Salous - Feed A Developer
AMH - Feed B Developer
Khatib - Generator Developer
Mounji - Realis


