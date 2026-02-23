import os
import time
from typing import Dict, List, Any, Optional

from fastavro import parse_schema, writer


class AvroSink:
    """
    Writes events to Avro Object Container Files (OCF) using fastavro.writer().
    Produces rolling files so each .avro file is independently valid.

    Example outputs:
      sample_data/avro/order_events_0001.avro
      sample_data/avro/order_events_0002.avro
    """

    def __init__(
        self,
        base_dir: str,
        schema_paths: Dict[str, str],
        max_records_per_file: int = 5000,
        codec: str = "deflate",
        file_prefix_ts: bool = False,
    ):
        """
        Args:
            base_dir: directory to write avro files into.
            schema_paths: mapping feed_name -> path to .avsc schema file.
                          e.g. {"order_events": "../schemas/order_events_v1.avsc", ...}
            max_records_per_file: roll to a new .avro file after N records per feed.
            codec: Avro codec ("null", "deflate", "snappy" if available).
            file_prefix_ts: if True, include epoch timestamp in filename for uniqueness.
        """
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

        self.max_records_per_file = max_records_per_file
        self.codec = codec
        self.file_prefix_ts = file_prefix_ts

        # Parsed schemas
        self.schemas: Dict[str, Any] = {}
        for feed, path in schema_paths.items():
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            # fastavro accepts dict schemas; file is JSON text
            import json
            schema_dict = json.loads(raw)
            self.schemas[feed] = parse_schema(schema_dict)

        # Per-feed rolling state
        self._buffers: Dict[str, List[Dict[str, Any]]] = {feed: [] for feed in schema_paths.keys()}
        self._file_index: Dict[str, int] = {feed: 1 for feed in schema_paths.keys()}
        self._record_count_in_file: Dict[str, int] = {feed: 0 for feed in schema_paths.keys()}

    def write_batch(self, feed_name: str, events: List[Dict[str, Any]]) -> None:
        """Buffer events and flush to disk when file size threshold is reached."""
        if not events:
            return

        if feed_name not in self.schemas:
            raise ValueError(f"Unknown feed_name '{feed_name}'. Known feeds: {list(self.schemas.keys())}")

        buf = self._buffers[feed_name]
        buf.extend(events)

        # Flush if we hit the per-file limit
        if self._record_count_in_file[feed_name] + len(buf) >= self.max_records_per_file:
            self._flush(feed_name)

    def close(self) -> None:
        """Flush all remaining buffered events to disk."""
        for feed in list(self._buffers.keys()):
            if self._buffers[feed]:
                self._flush(feed)

    def _next_filepath(self, feed_name: str) -> str:
        idx = self._file_index[feed_name]
        ts_part = f"{int(time.time())}_" if self.file_prefix_ts else ""
        filename = f"{feed_name}_{ts_part}{idx:04d}.avro"
        return os.path.join(self.base_dir, filename)

    def _flush(self, feed_name: str) -> None:
        records = self._buffers[feed_name]
        if not records:
            return

        # Write a new Avro container file (OCF)
        path = self._next_filepath(feed_name)
        schema = self.schemas[feed_name]

        with open(path, "wb") as out:
            writer(out, schema, records, codec=self.codec)

        # Update rolling counters
        self._buffers[feed_name] = []
        self._file_index[feed_name] += 1
        self._record_count_in_file[feed_name] = 0