import json
import os
from typing import Iterable


def write_jsonl(rows_iter: Iterable[dict], path: str):
  os.makedirs(os.path.dirname(path), exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    for r in rows_iter:
      f.write(json.dumps(r, ensure_ascii=False) + "\n")
