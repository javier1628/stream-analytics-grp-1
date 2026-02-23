import uuid

def new_event_id():
    return str(uuid.uuid4())

def new_order_id(rng):
    return f"ord_{rng.randint(100000, 999999)}"

def new_customer_id(rng):
    return f"cust_{rng.randint(10000, 99999)}"