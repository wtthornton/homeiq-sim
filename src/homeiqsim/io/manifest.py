import hashlib
import json
import os


def dataset_hash(meta: dict) -> str:
  s = json.dumps(meta, sort_keys=True).encode()
  return hashlib.sha256(s).hexdigest()[:16]


def write_manifest(path: str, meta: dict):
  os.makedirs(os.path.dirname(path), exist_ok=True)
  meta["dataset_hash"] = dataset_hash(meta)
  with open(path, "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
