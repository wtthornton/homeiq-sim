def synth_devices(total_devices: int, features: dict, region: str, rng) -> dict:
  """
  Return device counts by category. Very light heuristic split.
  """
  # Base shares
  shares = {
    "sensors": 0.35, "lights": 0.20, "switches": 0.15, "plugs": 0.10,
    "cameras": 0.06, "thermostats": 0.03, "media": 0.06, "other": 0.05
  }
  # Adjust for features
  if features.get("frigate"):
    shares["cameras"] += 0.03
    shares["sensors"] -= 0.02
  if features.get("energy_monitoring"):
    shares["plugs"] += 0.02
    shares["sensors"] += 0.01
  # Normalize
  total_share = sum(shares.values())
  for k in shares:
    shares[k] /= total_share
  # Allocate
  counts = {k: int(total_devices * v) for k, v in shares.items()}
  # Ensure sum == total_devices
  diff = total_devices - sum(counts.values())
  if diff:
    counts["other"] = counts.get("other", 0) + diff
  return counts
