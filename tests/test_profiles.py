from homeiqsim.core.rng import RNG
from homeiqsim.model.profiles import ProfileConfig, sample_profile_counts


def test_entities_to_devices_ratio_bounds():
  rng = RNG(42)
  pcfg = ProfileConfig(
    entities={"median": 540, "p90": 820},
    devices={"median": 85, "p90": 120},
    sensor_virtual_share=(0.5, 0.65),
  )
  out = sample_profile_counts("intermediate", pcfg, rng)
  ratio = out["total_entities"] / out["total_devices"]
  assert 3.5 <= ratio <= 7.5
