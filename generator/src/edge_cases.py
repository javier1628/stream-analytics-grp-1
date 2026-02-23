import random
from typing import List, Dict

class EdgeCaseInjector:
    def __init__(self, cfg, rng_seed: int):
        self.cfg = cfg
        self.rng = random.Random(rng_seed)

    def apply_to_orders(self, events: List[Dict], world, now_ms: int) -> List[Dict]:
        out = []
        for e in events:
            out.append(e)

            # Duplicate
            if self.rng.random() < self.cfg["edge_cases"]["duplicate_probability"]:
                out.append(e)  # exact same event (same event_id)

            # Late event: shift event_ts backwards
            if self.rng.random() < self.cfg["edge_cases"]["late_event_probability"]:
                delay_s = self.rng.randint(1, self.cfg["edge_cases"]["late_event_max_delay_s"])
                e_late = dict(e)
                e_late["event_ts_ms"] = e["event_ts_ms"] - delay_s * 1000
                out.append(e_late)

        # Missing steps / impossible durations are easier to implement in order_feed
        # (because they depend on lifecycle), but you can also inject here if desired.
        return out

    def apply_to_couriers(self, events: List[Dict], world, now_ms: int) -> List[Dict]:
        out = []
        for e in events:
            out.append(e)

            if self.rng.random() < self.cfg["edge_cases"]["duplicate_probability"]:
                out.append(e)

            if self.rng.random() < self.cfg["edge_cases"]["late_event_probability"]:
                delay_s = self.rng.randint(1, self.cfg["edge_cases"]["late_event_max_delay_s"])
                e_late = dict(e)
                e_late["event_ts_ms"] = e["event_ts_ms"] - delay_s * 1000
                out.append(e_late)

        return out