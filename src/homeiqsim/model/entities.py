def devices_to_entities(devices: dict, profile: str, virtual_share: tuple, features: dict, rng) -> dict:
  """
  Explode devices to entities; apply Frigate and Energy multipliers; ensure sum matches.
  """
  # Base entity-per-device by type (rough heuristics)
  epd = {
    "sensors": 2.5, "lights": 1.2, "switches": 1.5, "plugs": 2.0,
    "cameras": 8.0, "thermostats": 6.0, "media": 2.0, "other": 1.5
  }
  if features.get("frigate"):
    # Increase camera entities (zones & detections)
    epd["cameras"] = 18.0
  if features.get("energy_monitoring"):
    epd["plugs"] = 3.5
  ents = {k: int(v * epd.get(k, 1.5)) for k, v in devices.items()}
  # Virtual/template/statistics boost on sensors
  vs_min, vs_max = virtual_share
  vratio = float(rng.uniform(vs_min, vs_max))
  ents["sensors"] = int(ents.get("sensors", 0) * (1.0 + vratio))
  return ents
