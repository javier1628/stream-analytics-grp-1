import os
import json

class JsonlSink:
    def __init__(self, base_dir: str, feed_names):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.files = {name: open(os.path.join(base_dir, f"{name}.jsonl"), "a", encoding="utf-8")
                      for name in feed_names}

    def write_batch(self, feed_name: str, events):
        f = self.files[feed_name]
        for e in events:
            f.write(json.dumps(e) + "\n")

    def close(self):
        for f in self.files.values():
            f.close()