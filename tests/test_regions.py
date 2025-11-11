from homeiqsim.core.rng import RNG
from homeiqsim.model.regions import RegionConfig, sample_latitude


def test_latitude_sampling_in_range():
  rcfg = RegionConfig(
    lat_range=(25, 35),
    hvac_mult=1,
    dehum_mult=1,
    lighting_winter_mult=1,
    irrigation_mult=1,
    solar_mult=1,
    storm_burst_mult=1,
  )
  lat = sample_latitude(rcfg, RNG(1))
  assert 25 <= lat <= 35
