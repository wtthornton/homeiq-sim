from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import numpy as np


@dataclass
class WeatherDriver:
  region: str
  rng_seed: int = 0

  def hourly_series(self, year: int):
    # Synthetic hourly temp/humidity/precip flags via seasonal sine + noise
    rng = np.random.default_rng(self.rng_seed or 123)
    start = datetime(year,1,1,tzinfo=timezone.utc)
    end   = datetime(year+1,1,1,tzinfo=timezone.utc)
    d = start
    while d < end:
      doy = d.timetuple().tm_yday
      base = {
        "north": (5, 18),       # mean winter/summer C anchors
        "south": (12, 33),
        "arid_west": (7, 35),
        "marine_west": (8, 22),
        "east_midwest": (4, 30),
      }.get(self.region, (6, 28))
      winter, summer = base
      # seasonal temp curve (C)
      T = (winter + summer)/2 + ((summer - winter)/2)*math.sin(2*math.pi*(doy-172)/365)
      T += rng.normal(0, 2.5)  # noise
      # humidity (rough heuristic per region)
      RH_base = {
        "north": 0.55, "south": 0.70, "arid_west": 0.30,
        "marine_west": 0.75, "east_midwest": 0.60
      }.get(self.region, 0.55)
      RH = min(0.95, max(0.15, RH_base + rng.normal(0, 0.05)))
      precip = rng.random() < {"south":0.08,"marine_west":0.07,"east_midwest":0.06,"north":0.05,"arid_west":0.02}.get(self.region,0.05)
      yield d, {"temp_c": float(T), "rel_humidity": float(RH), "precip": bool(precip)}
      d += timedelta(hours=1)
