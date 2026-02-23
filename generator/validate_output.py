#!/usr/bin/env python3
"""
validate_output.py

Validates generated sample data for your food-delivery streaming generator.

Checks (JSONL + AVRO):
- File readable and non-empty
- Required fields present
- Basic type sanity (event_ts_ms int, ids strings)
- Duplicate events (same event_id appears > 1)
- Out-of-order / late-ish events (event_ts_ms goes backwards in file order)
- Order lifecycle sanity:
  - missing steps (DELIVERED without PICKED_UP)
  - impossible durations (DELIVERED_ts < PICKED_UP_ts, READY_ts < ACCEPTED_ts, etc.)
- Courier anomaly: OFFLINE while order_id is not None
- Joinability:
  - Order ASSIGNED events have courier_id
  - Courier ASSIGNED events have order_id
  - Assigned courier_events.order_id exists in order_events.order_id set

Usage (from generator/):
  python validate_output.py \
    --json-order sample_data/json/order_events.jsonl \
    --json-courier sample_data/json/courier_events.jsonl \
    --avro-order sample_data/avro/order_events_0001.avro \
    --avro-courier sample_data/avro/courier_events_0001.avro

If you have multiple avro files, you can pass a directory instead:
  python validate_output.py --avro-order sample_data/avro --avro-courier sample_data/avro

Exit code:
  0 = all checks passed (warnings allowed)
  2 = one or more FAIL checks
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from fastavro import reader as avro_reader
except Exception as e:
    avro_reader = None  # type: ignore


# ----------------------------
# Utility + Reporting
# ----------------------------

@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""


@dataclass
class Report:
    checks: List[CheckResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add(self, name: str, ok: bool, details: str = "") -> None:
        self.checks.append(CheckResult(name=name, ok=ok, details=details))

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def has_failures(self) -> bool:
        return any(not c.ok for c in self.checks)

    def print(self) -> None:
        width = max((len(c.name) for c in self.checks), default=10)
        print("\nVALIDATION REPORT")
        print("=" * 80)
        for c in self.checks:
            status = "PASS" if c.ok else "FAIL"
            line = f"{status:<5}  {c.name:<{width}}"
            if c.details:
                line += f"  - {c.details}"
            print(line)

        if self.warnings:
            print("\nWARNINGS")
            print("-" * 80)
            for w in self.warnings:
                print(f"- {w}")

        print("=" * 80)
        total = len(self.checks)
        fails = sum(1 for c in self.checks if not c.ok)
        print(f"Checks: {total} | Failures: {fails} | Warnings: {len(self.warnings)}\n")


# ----------------------------
# Readers
# ----------------------------

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i} in {path}: {e}") from e
    return records


def resolve_avro_paths(path_or_dir: str, feed_hint: str) -> List[str]:
    """
    If a directory is passed, try to pick matching files.
    """
    if os.path.isdir(path_or_dir):
        # Prefer files whose names include the feed hint (order/courier)
        pattern1 = os.path.join(path_or_dir, f"*{feed_hint}*.avro")
        matches = sorted(glob.glob(pattern1))
        if matches:
            return matches
        # Otherwise, take all .avro
        matches = sorted(glob.glob(os.path.join(path_or_dir, "*.avro")))
        return matches
    return [path_or_dir]


def read_avro(path_or_dir: str, feed_hint: str) -> List[Dict[str, Any]]:
    if avro_reader is None:
        raise RuntimeError(
            "fastavro is not installed. Install it with: pip install fastavro"
        )

    paths = resolve_avro_paths(path_or_dir, feed_hint=feed_hint)
    if not paths:
        return []

    out: List[Dict[str, Any]] = []
    for p in paths:
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        with open(p, "rb") as f:
            for rec in avro_reader(f):
                # fastavro may return dict-like records already
                out.append(dict(rec))
    return out


# ----------------------------
# Validation Logic
# ----------------------------

ORDER_REQUIRED = {
    "schema_version",
    "event_id",
    "event_ts_ms",
    "order_id",
    "event_type",
    "zone_id",
    "restaurant_id",
    "customer_id",
    "courier_id",
    "order_value_cents",
    "currency",
    "cancel_reason",
    "fail_reason",
}

COURIER_REQUIRED = {
    "schema_version",
    "event_id",
    "event_ts_ms",
    "courier_id",
    "zone_id",
    "status",
    "order_id",
}

ORDER_LIFECYCLE = ["CREATED", "ASSIGNED", "ACCEPTED", "PREPARING", "READY", "PICKED_UP", "DELIVERED"]


def basic_fields_check(records: List[Dict[str, Any]], required: Set[str]) -> Tuple[bool, str]:
    if not records:
        return False, "No records found"
    missing_counts: Dict[str, int] = {}
    for r in records:
        for k in required:
            if k not in r:
                missing_counts[k] = missing_counts.get(k, 0) + 1

    if missing_counts:
        worst = sorted(missing_counts.items(), key=lambda x: (-x[1], x[0]))[:5]
        return False, f"Missing fields (top): {worst}"
    return True, f"{len(records)} records"


def basic_type_sanity(records: List[Dict[str, Any]], id_fields: List[str]) -> Tuple[bool, str]:
    bad = 0
    for r in records:
        # event_ts_ms should be int-ish
        ts = r.get("event_ts_ms")
        if not isinstance(ts, int):
            bad += 1
            continue
        for f in id_fields:
            v = r.get(f)
            # allow None for nullable fields (like courier_id/order_id)
            if v is None:
                continue
            if not isinstance(v, str):
                bad += 1
                break
    if bad:
        return False, f"{bad} records failed type sanity"
    return True, "Types look sane"


def count_duplicates_by_event_id(records: List[Dict[str, Any]]) -> Tuple[int, int]:
    seen: Set[str] = set()
    dup = 0
    total = 0
    for r in records:
        eid = r.get("event_id")
        if not isinstance(eid, str):
            continue
        total += 1
        if eid in seen:
            dup += 1
        else:
            seen.add(eid)
    return dup, total


def count_out_of_order(records: List[Dict[str, Any]]) -> Tuple[int, Optional[int]]:
    """
    In file order, count how often event_ts_ms goes backwards.
    Returns (count_backwards, worst_negative_delta_ms)
    """
    last_ts: Optional[int] = None
    backwards = 0
    worst_delta: Optional[int] = None
    for r in records:
        ts = r.get("event_ts_ms")
        if not isinstance(ts, int):
            continue
        if last_ts is not None and ts < last_ts:
            backwards += 1
            delta = ts - last_ts
            if worst_delta is None or delta < worst_delta:
                worst_delta = delta
        last_ts = ts
    return backwards, worst_delta


def index_order_events(order_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """
    order_id -> event_type -> event_ts_ms (earliest observed for that event_type)
    """
    idx: Dict[str, Dict[str, int]] = {}
    for r in order_records:
        oid = r.get("order_id")
        et = r.get("event_type")
        ts = r.get("event_ts_ms")
        if not (isinstance(oid, str) and isinstance(et, str) and isinstance(ts, int)):
            continue
        m = idx.setdefault(oid, {})
        # keep earliest timestamp for that event_type
        if et not in m or ts < m[et]:
            m[et] = ts
    return idx


def count_missing_steps(order_idx: Dict[str, Dict[str, int]]) -> int:
    missing = 0
    for oid, evmap in order_idx.items():
        if "DELIVERED" in evmap and "PICKED_UP" not in evmap:
            missing += 1
    return missing


def count_impossible_durations(order_idx: Dict[str, Dict[str, int]]) -> Tuple[int, List[Tuple[str, str]]]:
    """
    Count orders where timestamp order is impossible.
    Returns count and a few example (order_id, reason).
    """
    bad = 0
    examples: List[Tuple[str, str]] = []
    for oid, evmap in order_idx.items():
        # compare a few key pairs if both exist
        pairs = [
            ("ASSIGNED", "CREATED"),
            ("ACCEPTED", "ASSIGNED"),
            ("READY", "ACCEPTED"),
            ("PICKED_UP", "READY"),
            ("DELIVERED", "PICKED_UP"),
        ]
        for later, earlier in pairs:
            if later in evmap and earlier in evmap and evmap[later] < evmap[earlier]:
                bad += 1
                if len(examples) < 5:
                    examples.append((oid, f"{later}({evmap[later]}) < {earlier}({evmap[earlier]})"))
                break
    return bad, examples


def joinability_checks(order_records: List[Dict[str, Any]], courier_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    order_ids: Set[str] = set()
    order_assigned_missing_courier = 0
    order_assigned_total = 0

    for r in order_records:
        oid = r.get("order_id")
        if isinstance(oid, str):
            order_ids.add(oid)
        if r.get("event_type") == "ASSIGNED":
            order_assigned_total += 1
            if r.get("courier_id") is None:
                order_assigned_missing_courier += 1

    courier_assigned_total = 0
    courier_assigned_missing_order = 0
    courier_assigned_order_not_found = 0
    offline_mid_delivery = 0

    for r in courier_records:
        status = r.get("status")
        oid = r.get("order_id")
        if status == "ASSIGNED":
            courier_assigned_total += 1
            if oid is None:
                courier_assigned_missing_order += 1
            elif isinstance(oid, str) and oid not in order_ids:
                courier_assigned_order_not_found += 1

        # anomaly scenario
        if status == "OFFLINE" and oid is not None:
            offline_mid_delivery += 1

    return {
        "order_ids_total": len(order_ids),
        "order_assigned_total": order_assigned_total,
        "order_assigned_missing_courier": order_assigned_missing_courier,
        "courier_assigned_total": courier_assigned_total,
        "courier_assigned_missing_order": courier_assigned_missing_order,
        "courier_assigned_order_not_found": courier_assigned_order_not_found,
        "offline_mid_delivery": offline_mid_delivery,
    }


# ----------------------------
# Main
# ----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-order", required=False, default="sample_data/json/order_events.jsonl")
    ap.add_argument("--json-courier", required=False, default="sample_data/json/courier_events.jsonl")
    ap.add_argument("--avro-order", required=False, default=None,
                    help="Path to an AVRO file OR a directory containing .avro files.")
    ap.add_argument("--avro-courier", required=False, default=None,
                    help="Path to an AVRO file OR a directory containing .avro files.")
    args = ap.parse_args()

    report = Report()

    # -------- JSON --------
    try:
        json_order = read_jsonl(args.json_order) if args.json_order else []
        report.add("JSON order_events readable", True, f"{len(json_order)} records from {args.json_order}")
    except Exception as e:
        report.add("JSON order_events readable", False, str(e))
        json_order = []

    try:
        json_courier = read_jsonl(args.json_courier) if args.json_courier else []
        report.add("JSON courier_events readable", True, f"{len(json_courier)} records from {args.json_courier}")
    except Exception as e:
        report.add("JSON courier_events readable", False, str(e))
        json_courier = []

    ok, details = basic_fields_check(json_order, ORDER_REQUIRED)
    report.add("JSON order_events required fields", ok, details)

    ok, details = basic_fields_check(json_courier, COURIER_REQUIRED)
    report.add("JSON courier_events required fields", ok, details)

    ok, details = basic_type_sanity(json_order, ["event_id", "order_id", "zone_id", "restaurant_id", "customer_id"])
    report.add("JSON order_events type sanity", ok, details)

    ok, details = basic_type_sanity(json_courier, ["event_id", "courier_id", "zone_id"])
    report.add("JSON courier_events type sanity", ok, details)

    dup, total = count_duplicates_by_event_id(json_order)
    report.add("JSON order_events duplicates present", dup > 0, f"{dup} duplicates out of {total} event_ids")

    dup, total = count_duplicates_by_event_id(json_courier)
    report.add("JSON courier_events duplicates present", dup > 0, f"{dup} duplicates out of {total} event_ids")

    backwards, worst = count_out_of_order(json_order)
    # late/out-of-order is expected; PASS if at least 1 backwards is present
    if worst is not None:
        report.add("JSON order_events out-of-order present", backwards > 0, f"{backwards} backwards; worst delta {worst} ms")
    else:
        report.add("JSON order_events out-of-order present", False, "No comparable timestamps found")

    backwards, worst = count_out_of_order(json_courier)
    if worst is not None:
        report.add("JSON courier_events out-of-order present", backwards > 0, f"{backwards} backwards; worst delta {worst} ms")
    else:
        report.add("JSON courier_events out-of-order present", False, "No comparable timestamps found")

    order_idx = index_order_events(json_order)
    miss = count_missing_steps(order_idx)
    report.add("Order missing-step edge case present", miss > 0, f"{miss} orders delivered without picked_up")

    bad, examples = count_impossible_durations(order_idx)
    report.add("Order impossible-duration edge case present", bad > 0, f"{bad} orders; examples: {examples[:3]}")

    joins = joinability_checks(json_order, json_courier)
    # These are "should pass" checks rather than "edge-case should exist"
    report.add(
        "Joinability: order ASSIGNED has courier_id",
        joins["order_assigned_total"] == 0 or joins["order_assigned_missing_courier"] == 0,
        f"assigned={joins['order_assigned_total']}, missing_courier={joins['order_assigned_missing_courier']}"
    )
    report.add(
        "Joinability: courier ASSIGNED has order_id",
        joins["courier_assigned_total"] == 0 or joins["courier_assigned_missing_order"] == 0,
        f"assigned={joins['courier_assigned_total']}, missing_order={joins['courier_assigned_missing_order']}"
    )
    report.add(
        "Joinability: courier ASSIGNED order_id exists in order_events",
        joins["courier_assigned_total"] == 0 or joins["courier_assigned_order_not_found"] == 0,
        f"assigned={joins['courier_assigned_total']}, not_found={joins['courier_assigned_order_not_found']}"
    )

    # anomaly scenario (should exist if configured)
    report.add(
        "Courier offline-mid-delivery anomaly present",
        joins["offline_mid_delivery"] > 0,
        f"offline_with_order_id={joins['offline_mid_delivery']}"
    )

    # -------- AVRO (optional) --------
    if args.avro_order or args.avro_courier:
        if avro_reader is None:
            report.add("AVRO support (fastavro installed)", False, "Install fastavro: pip install fastavro")
        else:
            # Read AVRO
            avro_order: List[Dict[str, Any]] = []
            avro_courier: List[Dict[str, Any]] = []

            if args.avro_order:
                try:
                    avro_order = read_avro(args.avro_order, feed_hint="order")
                    report.add("AVRO order_events readable", True, f"{len(avro_order)} records from {args.avro_order}")
                except Exception as e:
                    report.add("AVRO order_events readable", False, str(e))

            if args.avro_courier:
                try:
                    avro_courier = read_avro(args.avro_courier, feed_hint="courier")
                    report.add("AVRO courier_events readable", True, f"{len(avro_courier)} records from {args.avro_courier}")
                except Exception as e:
                    report.add("AVRO courier_events readable", False, str(e))

            # Basic checks on AVRO too
            if avro_order:
                ok, details = basic_fields_check(avro_order, ORDER_REQUIRED)
                report.add("AVRO order_events required fields", ok, details)

            if avro_courier:
                ok, details = basic_fields_check(avro_courier, COURIER_REQUIRED)
                report.add("AVRO courier_events required fields", ok, details)

            # Optional: compare record counts (warning only, because you may generate different batches)
            if json_order and avro_order:
                report.warn(f"JSON order_events={len(json_order)} vs AVRO order_events={len(avro_order)} (may differ if you wrote different batches)")
            if json_courier and avro_courier:
                report.warn(f"JSON courier_events={len(json_courier)} vs AVRO courier_events={len(avro_courier)} (may differ if you wrote different batches)")

    report.print()

    return 2 if report.has_failures() else 0


if __name__ == "__main__":
    raise SystemExit(main())