class SimClock:
    def __init__(self, cfg):
        self.start_ts = cfg["simulation"]["start_ts_ms"]
        self.tick_ms = cfg["simulation"]["tick_ms"]
        self.duration_s = cfg["simulation"]["duration_s"]

        self.current_ts = self.start_ts
        self.end_ts = self.start_ts + self.duration_s * 1000

    def now_ms(self):
        return self.current_ts

    def tick(self):
        self.current_ts += self.tick_ms

    def running(self):
        return self.current_ts < self.end_ts