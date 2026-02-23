from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import random


@dataclass
class Restaurant:
    restaurant_id: str
    zone_id: str

@dataclass
class Courier:
    courier_id: str
    zone_id: str
    status: str  # ONLINE/OFFLINE/IDLE/ASSIGNED
    active_order_id: Optional[str] = None

@dataclass
class Order:
    order_id: str
    zone_id: str
    restaurant_id: str
    customer_id: str
    courier_id: Optional[str] = None
    state: str = "CREATED"
    state_ts_ms: Dict[str, int] = field(default_factory=dict)

    # NEW: planned schedule for realistic timing
    plan_ts_ms: Dict[str, int] = field(default_factory=dict)

    # NEW: prevent emitting same milestone twice
    emitted: Set[str] = field(default_factory=set)

class WorldState:
    def __init__(self, cfg, rng_seed: int):
        self.cfg = cfg
        self.rng = random.Random(rng_seed)

        self.zones = [f"zone_{i:02d}" for i in range(cfg["entities"]["num_zones"])]
        self.restaurants: List[Restaurant] = self._init_restaurants()
        self.couriers: Dict[str, Courier] = self._init_couriers()
        self.orders: Dict[str, Order] = {}

        # Useful lookup
        self.zone_to_restaurants: Dict[str, List[str]] = self._build_zone_restaurant_map()

    def _init_restaurants(self) -> List[Restaurant]:
        restaurants = []
        for i in range(self.cfg["entities"]["num_restaurants"]):
            zone_id = self.rng.choice(self.zones)
            restaurants.append(Restaurant(f"rest_{i:04d}", zone_id))
        return restaurants

    def _init_couriers(self) -> Dict[str, Courier]:
        couriers = {}
        for i in range(self.cfg["entities"]["num_couriers"]):
            zone_id = self.rng.choice(self.zones)
            # start mix of ONLINE/IDLE
            status = "ONLINE" if self.rng.random() < 0.8 else "OFFLINE"
            couriers[f"cour_{i:04d}"] = Courier(f"cour_{i:04d}", zone_id, status, None)
        return couriers

    def _build_zone_restaurant_map(self):
        m = {z: [] for z in self.zones}
        for r in self.restaurants:
            m[r.zone_id].append(r.restaurant_id)
        return m