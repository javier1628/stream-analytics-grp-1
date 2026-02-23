# Milestone 1: Quick Reference Checklist

## ✅ Requirement Fulfillment

### 1.1 Create Two Feeds
- [x] Feed A: `order_events` (order lifecycle)
- [x] Feed B: `courier_events` (courier availability/assignment)
- [x] Justified in documentation
- [x] Analytics use cases defined (basic/intermediate/advanced)
- [x] Schema supports event-time processing and late data

**Status: ✅ COMPLETE**

---

### 1.2 Schema & Formats

#### AVRO Schemas
- [x] `courier_events_v1.avsc` – well-formed AVRO record
- [x] `order_events_v1.avsc` – well-formed AVRO record
- [x] Versioning: `schema_version` field present
- [x] Enums: `OrderEventType` (10 values), `CourierStatus` (4 values)
- [x] Optional fields: union types (null | string/int)

#### Event-Time & Identifiers
- [x] `event_ts_ms` (epoch milliseconds, logicalType=timestamp-millis)
- [x] Join identifiers: `order_id`, `courier_id`, `restaurant_id`, `zone_id`, `customer_id`
- [x] Deduplication support: `event_id` (UUID, globally unique)

#### Event Generation
- [x] JSON events generated (764+ lines in `order_events.jsonl`)
- [ ] **AVRO events NOT generated** (no .avro files; critical gap)

**Status: ⚠️ PARTIAL (JSON ✅, AVRO ❌)**

---

### 1.3 Realism Requirements

#### Distributions
- [x] Lunch peak (12–14h): 1.6x multiplier
- [x] Dinner peak (19–21h): 1.8x multiplier
- [x] Weekday/weekend variation: multipliers in config
- [ ] Zone-level skew: configured but NOT applied (uniform selection used)

#### Configurability
- [x] Number of restaurants: `num_restaurants`
- [x] Number of couriers: `num_couriers`
- [x] Number of zones: `num_zones`
- [x] Base demand rate: `base_orders_per_min`
- [x] Cancellation probability: `cancel_probability`
- [x] Surge periods: `surge` config section
- [x] Edge case probabilities: all exposed

**Status: ✅ GOOD**

#### Edge Cases
- [x] **Out-of-order events** – implemented (5% late probability, up to 10 min delay)
- [x] **Duplicates** – implemented (0.5% duplicate probability)
- [x] **Missing steps** – config flag exists; NOT wired
- [ ] **Impossible durations** – config flag exists; NOT implemented
- [ ] **Courier offline mid-delivery** – config flag exists; NOT fully implemented

**Status: ⚠️ PARTIAL (2/5 working, 3 flags defined but not wired)**

---

### 1.4 Deliverables

#### Professional GitHub Repository
- [x] Private repo: `stream-analytics-grp-1`
- [x] Comprehensive README (11 sections, 363 lines)
- [x] Team structure documented

#### Feed Generator
- [x] Python code: 8 modules + 1 config
- [x] Clean architecture (main → world → feeds → sink)
- [x] README with architecture overview

#### AVRO Schemas
- [x] Both schemas defined as `.avsc` files

#### Sample Data
- [x] JSON samples: `order_events.jsonl`, `courier_events.jsonl`
- [ ] AVRO samples: NOT in `/generator/sample_data/avro/`

**Status: ⚠️ PARTIAL (JSON ✅, AVRO ❌)**

---

## 📊 Overall Scoring

| Criterion | Points | Score | Notes |
|-----------|--------|-------|-------|
| Feed Design | 15 | 15 | Excellent justification |
| Schema Design | 15 | 14 | Excellent; missing AVRO generation |
| JSON Generation | 15 | 15 | Complete, realistic |
| AVRO Generation | 15 | 0 | Not implemented |
| Edge Cases | 15 | 10 | Late/duplicates work; 3/5 unimplemented |
| Configurability | 10 | 9 | Most params exposed; some not applied |
| Documentation | 10 | 10 | Comprehensive, professional |
| Code Quality | 5 | 5 | Well-structured, modular |
| **TOTAL** | **100** | **78** | **Pass with gaps** |

---

## 🔴 Critical Issues

### 1. **AVRO Binary Not Generated**
   - **Impact:** Requirement 1.2 unfulfilled; Event Hubs in M2 may expect AVRO
   - **Fix:** Implement `AvroSink` class using `fastavro` library
   - **Time:** ~1 hour
   - **Status:** Must fix before final submission

---

## 🟡 Medium-Priority Issues

### 2. **Edge Case Flags Not Wired**
   - **Missing steps:** Config flag but no logic
   - **Impossible durations:** Config flag but no logic
   - **Courier offline mid-delivery:** Config flag but incomplete logic
   - **Impact:** Watermark/anomaly detection testing in M2 may be hampered
   - **Fix:** Add ~20 lines per edge case
   - **Time:** ~2 hours
   - **Status:** Should complete before M2

### 3. **Time-of-Day Variation Not Applied**
   - **Impact:** `orders_this_tick()` ignores lunch/dinner peak multipliers
   - **Fix:** Apply multiplier based on hour of day
   - **Time:** ~30 minutes
   - **Status:** Nice-to-have for realism

### 4. **Zone-Level Skew Not Applied**
   - **Impact:** `choose_zone_weighted()` uses uniform selection despite config
   - **Fix:** Use Dirichlet or weighted sampling
   - **Time:** ~30 minutes
   - **Status:** Nice-to-have for realism

---

## 💡 Key Strengths

1. **Excellent feed design:** Two complementary feeds (demand + supply) with clear analytics vision
2. **Professional schemas:** Proper versioning, enums, optional fields, event-time support
3. **Comprehensive documentation:** README covers all aspects from design to assumptions
4. **Strong architecture:** Modular code with clear separation of concerns
5. **Working edge cases:** Late arrivals and duplicates successfully injected
6. **Realistic behavior:** Cancellations, failures, peaks modeled

---

## ✏️ Action Items (Priority Order)

### Immediate (Before M2 Starts)
- [ ] Implement `AvroSink` class
- [ ] Generate AVRO sample files
- [ ] Wire "missing steps" edge case
- [ ] Wire "impossible durations" edge case
- [ ] Wire "courier offline mid-delivery" edge case

### Desirable (Before M2 Starts)
- [ ] Apply time-of-day demand variation
- [ ] Apply zone-level demand skew
- [ ] Improve Poisson sampling

### Nice-to-Have (After M2)
- [ ] Add test suite for generator
- [ ] Add visualization of generated metrics
- [ ] Parameterize state transition probabilities

---

## 📋 Files Status

```
✅ generator/config.yaml                    – Complete, well-structured
✅ generator/README.md                      – Excellent documentation
✅ generator/src/main.py                    – Working entry point
✅ generator/src/world.py                   – Good entity pools
✅ generator/src/clocks.py                  – Working simulation clock
✅ generator/src/ids.py                     – Good ID generation
⚠️ generator/src/distributions.py           – Incomplete (missing time-of-day/skew)
✅ generator/src/edge_cases.py              – Partially implemented
✅ generator/src/feeds/order_feed.py        – Working lifecycle logic
✅ generator/src/feeds/courier_feed.py      – Working state transitions
❌ generator/src/sinks/avro_sink.py         – NOT IMPLEMENTED
✅ generator/src/sinks/jsonl_sink.py        – Complete
✅ avro_schema/courier_events_v1.avsc       – Excellent
✅ avro_schema/order_events_v1.avsc         – Excellent
✅ generator/sample_data/json/*.jsonl       – Complete
❌ generator/sample_data/avro/*.avro        – MISSING
✅ README.md                                 – Excellent
✅ GitHub repo                               – Properly set up
```

---

## 🎯 Recommended Workflow for Fixes

1. **Day 1:** Implement `AvroSink` → test → generate AVRO samples
2. **Day 2:** Wire 3 edge cases → validate configs → test generator
3. **Day 3:** (Optional) Apply time-of-day + zone skew → validate distributions
4. **Day 4:** Final testing + documentation updates

---

## 📞 Questions for Instructor Review

1. Should AVRO samples be in same format as JSON (one record per line in binary)? Or full AVRO container?
2. For "impossible durations," should these be probabilistically injected per order, or deterministically at generation time?
3. Should missing steps skip directly to next state, or insert intermediate state with earlier timestamp?

---

**Generated:** 23 February 2026  
**Assessment Version:** 1.0  
**Recommended Action:** Fix AVRO generation, wire edge cases, then proceed to M2
