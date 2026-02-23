from typing import List, Dict
from ids import new_event_id
from world import WorldState

class CourierFeed:
    def __init__(self, cfg):
        self.cfg = cfg

    def step(self, world: WorldState, now_ms: int) -> List[Dict]:
        events = []
        edge = self.cfg.get("edge_cases", {})
        p_offline_mid = edge.get("courier_offline_mid_delivery_probability", 0.0)
        p_recover = edge.get("courier_recover_probability", 0.0)

        for c in world.couriers.values():

            # 1) Anomaly: courier goes OFFLINE mid-delivery (ASSIGNED with active_order_id)
            if c.active_order_id is not None and c.status == "ASSIGNED":
                if world.rng.random() < p_offline_mid:
                    c.status = "OFFLINE"
                    events.append(self._emit(now_ms, c, order_id=c.active_order_id))
                    # IMPORTANT: keep active_order_id set (so anomaly is observable)
                    continue

            # 2) Recovery: come back ONLINE after being OFFLINE (can still have active order)
            if c.status == "OFFLINE" and world.rng.random() < p_recover:
                c.status = "ONLINE"
                # include order_id if still carrying it
                events.append(self._emit(now_ms, c, order_id=c.active_order_id))

            # 3) Normal OFFLINE toggle ONLY if no job (avoid accidental mid-delivery anomaly)
            if c.status == "ONLINE" and c.active_order_id is None and world.rng.random() < 0.01:
                c.status = "OFFLINE"
                events.append(self._emit(now_ms, c, order_id=None))

            # 4) Optional ONLINE ↔ IDLE toggles (only if no job)
            if c.status == "ONLINE" and c.active_order_id is None and world.rng.random() < 0.05:
                c.status = "IDLE"
                events.append(self._emit(now_ms, c, order_id=None))

            if c.status == "IDLE" and world.rng.random() < 0.05:
                c.status = "ONLINE"
                events.append(self._emit(now_ms, c, order_id=None))

            # 5) If courier got assigned by OrderFeed, emit that state once per tick
            if c.status == "ASSIGNED":
                events.append(self._emit(now_ms, c, order_id=c.active_order_id))
                

        return events

    def _emit(self, now_ms, courier, order_id):
        return {
            "schema_version": 1,
            "event_id": new_event_id(),
            "event_ts_ms": now_ms,
            "courier_id": courier.courier_id,
            "zone_id": courier.zone_id,
            "status": courier.status,
            "order_id": order_id
        }