from typing import Tuple

from pydantic import BaseModel


class ProfileConfig(BaseModel):
  entities: dict
  devices: dict
  sensor_virtual_share: Tuple[float, float]


def sample_profile_counts(profile: str, cfg: ProfileConfig, rng) -> dict:
  ents = int(max(50, rng.lognormal_by_median_p90(cfg.entities["median"], cfg.entities["p90"])))
  devs = int(max(10,  rng.lognormal_by_median_p90(cfg.devices["median"],  cfg.devices["p90"])))
  # Enforce 47 ents/device by rescaling devices if needed
  ratio = ents / max(1, devs)
  if ratio < 4.0:
    devs = max(1, int(ents/4.0))
  elif ratio > 7.0:
    devs = max(1, int(ents/7.0))
  return {"total_entities": ents, "total_devices": devs}
