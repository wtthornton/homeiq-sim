from typing import Tuple

from pydantic import BaseModel


class RegionConfig(BaseModel):
  lat_range: Tuple[float, float]
  hvac_mult: float
  dehum_mult: float
  lighting_winter_mult: float
  irrigation_mult: float
  solar_mult: float
  storm_burst_mult: float


def sample_latitude(rcfg: RegionConfig, rng) -> float:
  low, high = rcfg.lat_range
  return float(rng.uniform(low, high))
