import os
from typing import Iterable

import pyarrow as pa
import pyarrow.parquet as pq


def write_events_parquet(rows_iter: Iterable[dict], path: str, schema_version: str, shard_idx: int):
  os.makedirs(os.path.dirname(path), exist_ok=True)
  rows = list(rows_iter)
  if not rows:
    return
  batch = pa.Table.from_pylist(rows)
  pq.write_table(batch, path, compression="snappy")
