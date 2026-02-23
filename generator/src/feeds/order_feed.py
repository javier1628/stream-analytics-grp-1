from typing import List, Dict
from ids import new_event_id, new_order_id, new_customer_id
from distributions import orders_this_tick, choose_zone_weighted
from world import WorldState, Order
from durations import sample_prep_time_s, sample_pickup_wait_s, sample_delivery_time_s


ORDER_EVENT_TYPES = [
    "CREATED","ASSIGNED","ACCEPTED","PREPARING","READY",
    "PICKED_UP","DELIVERED","CANCELLED","FAILED","REFUNDED"
]
LIFECYCLE_ORDER = ["ASSIGNED", "ACCEPTED", "PREPARING", "READY", "PICKED_UP", "DELIVERED"]
TERMINAL_STATES = ("DELIVERED", "CANCELLED", "FAILED", "REFUNDED")

class OrderFeed:
    def __init__(self, cfg):
        self.cfg = cfg

    @staticmethod
    def _prob_per_tick(p_per_min: float, tick_ms: int) -> float:
        return 1.0 - (1.0 - p_per_min) ** (tick_ms / 60000.0)

    def step(self, world: WorldState, now_ms: int) -> List[Dict]:
        events = []

        # 1) Create new orders (demand)
        n_new = orders_this_tick(self.cfg, now_ms, world.rng)
        for _ in range(n_new):
            zone_id = choose_zone_weighted(self.cfg, world, world.rng)
            restaurant_id = world.rng.choice(world.zone_to_restaurants[zone_id])
            order_id = new_order_id(world.rng)
            customer_id = new_customer_id(world.rng)

            order = Order(
                order_id=order_id,
                zone_id=zone_id,
                restaurant_id=restaurant_id,
                customer_id=customer_id,
                state="CREATED",
                state_ts_ms={"CREATED": now_ms}
            )

            order.plan_ts_ms = self._build_order_plan(now_ms, world.rng)
            order.emitted.add("CREATED")

            world.orders[order_id] = order

            events.append(self._emit(now_ms, order, "CREATED"))

        # 2) Advance existing orders
        for order in list(world.orders.values()):
            events.extend(self._maybe_advance_order(world, order, now_ms))

        return events

    def _maybe_advance_order(self, world: WorldState, order: Order, now_ms: int) -> List[Dict]:
        out: List[Dict] = []

        # Terminal states: do nothing
        if order.state in ("DELIVERED", "REFUNDED"):
            return out

        # Safety: if some orders exist without plan (older runs), create one once
        if not order.plan_ts_ms:
            created_ts = order.state_ts_ms.get("CREATED", now_ms)
            order.plan_ts_ms = self._build_order_plan(created_ts, world.rng)

        # Keep your cancel/fail/refund logic for now (later you can schedule these too)
        out.extend(self._maybe_cancel_fail_refund(world, order, now_ms))
        if order.state in ("CANCELLED", "FAILED", "REFUNDED"):
            # If order ended and a courier was assigned, release them
            if order.courier_id:
                self._release_courier(world, order.courier_id)
            return out

        # Emit lifecycle milestones in order when their planned time is reached
        for milestone in LIFECYCLE_ORDER:
            if milestone in order.emitted:
                continue

            planned_ts = order.plan_ts_ms.get(milestone)
            if planned_ts is None:
                continue

            # If this milestone isn't due yet, later milestones won't be due either
            if now_ms < planned_ts:
                break

            # ASSIGNED requires a courier. If none available, retry in later ticks.
            if milestone == "ASSIGNED" and order.courier_id is None:
                courier_id = self._assign_courier(world, order.zone_id, order.order_id)
                if courier_id is None:
                    return out
                order.courier_id = courier_id

            # Update state using PLANNED event-time (not now_ms)
            order.state = milestone
            order.state_ts_ms[milestone] = planned_ts
            order.emitted.add(milestone)

            out.append(self._emit(planned_ts, order, milestone))

            # If delivered, release courier
            if milestone == "DELIVERED" and order.courier_id:
                self._release_courier(world, order.courier_id)

        return out
    
    def _maybe_cancel_fail_refund(self, world, order, now_ms):
        out = []

        tick_ms = self.cfg["simulation"]["tick_ms"]

        p_cancel = self._prob_per_tick(
            self.cfg["behavior"]["cancel_probability"],
            tick_ms
        )

        p_fail = self._prob_per_tick(
            self.cfg["behavior"]["fail_probability"],
            tick_ms
        )

        p_refund = self._prob_per_tick(
            self.cfg["behavior"]["refund_probability_given_cancel_or_fail"],
            tick_ms
        )

        if order.state in ("CREATED","ASSIGNED","ACCEPTED","PREPARING","READY") \
        and world.rng.random() < p_cancel:

            order.state = "CANCELLED"
            order.state_ts_ms["CANCELLED"] = now_ms
            out.append(self._emit(now_ms, order, "CANCELLED", cancel_reason="CUSTOMER_CANCELLED"))

        if order.state in ("ASSIGNED","ACCEPTED","PREPARING","READY","PICKED_UP") \
        and world.rng.random() < p_fail:

            order.state = "FAILED"
            order.state_ts_ms["FAILED"] = now_ms
            out.append(self._emit(now_ms, order, "FAILED", fail_reason="COURIER_NO_SHOW"))

        if order.state in ("CANCELLED","FAILED") \
        and world.rng.random() < p_refund:

            order.state = "REFUNDED"
            order.state_ts_ms["REFUNDED"] = now_ms
            out.append(self._emit(now_ms, order, "REFUNDED"))

        return out

    def _assign_courier(self, world: WorldState, zone_id: str, order_id: str):
        candidates = [
            c for c in world.couriers.values()
            if c.zone_id == zone_id and c.status in ("ONLINE", "IDLE") and c.active_order_id is None
        ]
        if not candidates:
            return None

        courier = world.rng.choice(candidates)
        courier.status = "ASSIGNED"
        courier.active_order_id = order_id  # IMPORTANT: keep join key in world state
        return courier.courier_id
    
    def _release_courier(self, world: WorldState, courier_id: str) -> None:
        c = world.couriers.get(courier_id)
        if not c:
            return
        c.active_order_id = None
        if c.status != "OFFLINE":
            c.status = "IDLE"

    def _emit(self, event_ts_ms, order: Order, event_type: str, cancel_reason=None, fail_reason=None):
        return {
            "schema_version": 1,
            "event_id": new_event_id(),
            "event_ts_ms": event_ts_ms,
            "order_id": order.order_id,
            "event_type": event_type,
            "zone_id": order.zone_id,
            "restaurant_id": order.restaurant_id,
            "customer_id": order.customer_id,
            "courier_id": order.courier_id,
            "order_value_cents": None,
            "currency": None,
            "cancel_reason": cancel_reason,
            "fail_reason": fail_reason
        }
    

    @staticmethod
    def _build_order_plan(now_ms: int, rng) -> dict:
        # assignment + accept happen quickly (seconds)
        assign_s = rng.randint(5, 45)
        accept_s = rng.randint(10, 120)

        prep_s = sample_prep_time_s(rng)
        pickup_wait_s = sample_pickup_wait_s(rng)
        delivery_s = sample_delivery_time_s(rng)

        t_assigned = now_ms + assign_s * 1000
        t_accepted = t_assigned + accept_s * 1000

        # PREPARING shortly after ACCEPTED
        t_preparing = t_accepted + rng.randint(5, 60) * 1000

        t_ready = t_accepted + prep_s * 1000
        t_picked = t_ready + pickup_wait_s * 1000
        t_delivered = t_picked + delivery_s * 1000

        return {
            "ASSIGNED": t_assigned,
            "ACCEPTED": t_accepted,
            "PREPARING": t_preparing,
            "READY": t_ready,
            "PICKED_UP": t_picked,
            "DELIVERED": t_delivered
        }