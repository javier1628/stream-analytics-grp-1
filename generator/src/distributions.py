import random
from datetime import datetime

def orders_this_tick(cfg, now_ms, rng):
    base = cfg["demand"]["base_orders_per_min"]
    # convert per minute to per tick
    tick_ms = cfg["simulation"]["tick_ms"]
    per_tick = base * (tick_ms / 60000.0)

    return rng.poisson(per_tick) if hasattr(rng, "poisson") else int(rng.random() < per_tick)

def choose_zone_weighted(cfg, world, rng):
    return rng.choice(world.zones)
