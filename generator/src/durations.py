import random

def sample_prep_time_s(rng: random.Random) -> int:
    # Typical prep: 5–20 minutes, skewed toward ~10–12
    return int(max(60, rng.lognormvariate(2.3, 0.4)))  # ~10 min median-ish

def sample_pickup_wait_s(rng: random.Random) -> int:
    # Wait between READY and PICKED_UP: 1–8 minutes
    return int(max(30, rng.lognormvariate(1.5, 0.5)))

def sample_delivery_time_s(rng: random.Random) -> int:
    # From PICKED_UP to DELIVERED: 8–30 minutes
    return int(max(120, rng.lognormvariate(2.7, 0.35)))