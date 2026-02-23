from config import load_config
from world import WorldState
from feeds.order_feed import OrderFeed
from feeds.courier_feed import CourierFeed
from edge_cases import EdgeCaseInjector
from sinks.jsonl_sink import JsonlSink
from clocks import SimClock
from sinks.avro_sink import AvroSink

def main():
    cfg = load_config("config.yaml")

    clock = SimClock(cfg)
    world = WorldState(cfg, rng_seed=cfg["seed"])

    order_feed = OrderFeed(cfg)
    courier_feed = CourierFeed(cfg)
    injector = EdgeCaseInjector(cfg, rng_seed=cfg["seed"] + 1)

    sink = JsonlSink(
        base_dir=cfg["simulation"]["emit_to"],
        feed_names=["order_events", "courier_events"]
    )

    avro_sink = AvroSink(
        base_dir="sample_data/avro",
        schema_paths={
            "order_events": "../avro_schema/order_events_v1.avsc",
            "courier_events": "../avro_schema/courier_events_v1.avsc",
        },
        max_records_per_file=2000,  # adjust as you like
        codec="deflate",
    )

    # main loop
    while clock.running():
        now_ms = clock.now_ms()

        # Step feeds (they mutate world + emit events)
        order_events = order_feed.step(world, now_ms)
        courier_events = courier_feed.step(world, now_ms)

        # Inject edge cases (late/out-of-order/duplicates/etc.)
        order_events = injector.apply_to_orders(order_events, world, now_ms)
        courier_events = injector.apply_to_couriers(courier_events, world, now_ms)

        # Write events
        sink.write_batch("order_events", order_events)
        sink.write_batch("courier_events", courier_events)

        avro_sink.write_batch("order_events", order_events)
        avro_sink.write_batch("courier_events", courier_events)


        clock.tick()

    sink.close()
    avro_sink.close()

if __name__ == "__main__":
    main()