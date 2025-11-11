import json
from pathlib import Path

import click
import yaml

from ..core.daylight import Daylight
from ..core.rng import RNG
from ..core.timebase import Timebase
from ..core.weather import WeatherDriver
from ..io.manifest import write_manifest
from ..io.write_parquet import write_events_parquet
from ..model.devices import synth_devices
from ..model.entities import devices_to_entities
from ..model.profiles import ProfileConfig, sample_profile_counts
from ..model.regions import RegionConfig, sample_latitude
from ..synth.events import synth_day_events
from ..synth.faults import inject_faults
from ..synth.labels import synth_labels


@click.command()
@click.option("--config", required=True, type=click.Path(exists=True))
def main(config):
  cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
  seed = int(cfg.get("seed", 42))
  rng = RNG(seed)
  year = int(cfg.get("year", 2025))
  output_cfg = cfg.get("output", {})
  out_dir = Path(output_cfg.get("path", "out/"))
  shards_per_month = int(output_cfg.get("shards_per_month", 8))
  base_path = Path(__file__).parent.parent
  profiles_yaml = yaml.safe_load((base_path / "config" / "profiles.yaml").read_text(encoding="utf-8"))
  regions_yaml = yaml.safe_load((base_path / "config" / "regions.yaml").read_text(encoding="utf-8"))
  profiles_cfg = {k: ProfileConfig(**v) for k, v in profiles_yaml["profiles"].items()}
  regions_cfg = {k: RegionConfig(**v) for k, v in regions_yaml["regions"].items()}
  homes_cfg = cfg.get("homes", {})
  counts = homes_cfg.get("counts", {})
  region_mix = homes_cfg.get("region_mix", {})
  feature_probs = cfg.get("feature_probs", homes_cfg.get("feature_probs", {}))
  occupancy_cfg = cfg.get("occupancy_profiles", {})
  homes = []
  region_keys = list(region_mix.keys())
  region_weights = [region_mix[k] for k in region_keys] if region_keys else []
  for prof, n in counts.items():
    for i in range(n):
      region = rng.choice(region_keys, p=region_weights) if region_keys else next(iter(regions_cfg))
      rcfg = regions_cfg[region]
      lat = sample_latitude(rcfg, rng)
      pcfg = profiles_cfg[prof]
      totals = sample_profile_counts(prof, pcfg, rng)
      features = {
        "frigate": rng.uniform(0, 1) < feature_probs.get("frigate", 0.0),
        "solar": rng.uniform(0, 1) < feature_probs.get("solar", 0.0),
        "irrigation": rng.uniform(0, 1) < feature_probs.get("irrigation", 0.0),
        "energy_monitoring": rng.uniform(0, 1) < feature_probs.get("energy_monitoring", 0.0),
      }
      wfh_low, wfh_high = occupancy_cfg.get("wfh_ratio", (0.2, 0.5))
      homes.append({
        "home_id": f"{prof[:3]}_{region}_{i:03d}",
        "profile": prof,
        "region": region,
        "latitude": lat,
        "totals": totals,
        "features": features,
        "region_mults": rcfg.model_dump(),
        "wfh_ratio": float(rng.uniform(wfh_low, wfh_high) if wfh_low != wfh_high else wfh_low),
        "has_kids": rng.uniform(0, 1) < occupancy_cfg.get("has_kids_probability", 0.5),
      })
  tb = Timebase(year)
  registry = {}
  for h in homes:
    devs = synth_devices(h["totals"]["total_devices"], h["features"], h["region"], rng)
    vs_min, vs_max = profiles_cfg[h["profile"]].sensor_virtual_share
    ents = devices_to_entities(devs, h["profile"], (vs_min, vs_max), h["features"], rng)
    target = h["totals"]["total_entities"]
    current = sum(ents.values())
    if current > 0 and current != target:
      scale = target / current
      ents = {k: max(0, int(v * scale)) for k, v in ents.items()}
      diff = target - sum(ents.values())
      if diff:
        key = max(ents, key=lambda k: ents[k])
        ents[key] += diff
    registry[h["home_id"]] = {"devices": devs, "entities": ents}
  daylight_map = {h["home_id"]: Daylight(latitude=h["latitude"]) for h in homes}
  weather_cache = {}
  for h in homes:
    driver = WeatherDriver(region=h["region"], rng_seed=seed + 1)
    series = {dt: payload for dt, payload in driver.hourly_series(year)}
    weather_cache[h["home_id"]] = series
  meta_counts = {"months": {}, "homes": len(homes), "year": year}
  for month in range(1, 13):
    shards = [[] for _ in range(shards_per_month)]
    for d in tb.days():
      if d.month != month:
        continue
      for h in homes:
        home_id = h["home_id"]
        sunrise, sunset = daylight_map[home_id].sunrise_sunset(d)
        def weather_fn(ts, home_id=home_id):
          hour = ts.replace(minute=0, second=0, microsecond=0)
          cache = weather_cache[home_id]
          if hour not in cache:
            hour = max(k for k in cache.keys() if k <= hour)
          return cache[hour]
        day_ctx = {
          "home_id": home_id,
          "date": d,
          "sunrise": sunrise,
          "sunset": sunset,
          "region": h["region"],
          "region_mults": h["region_mults"],
          "year": year,
        }
        ents = registry[home_id]["entities"]
        events = synth_day_events(day_ctx, ents, {"weather": weather_fn}, rng)
        events = inject_faults(events, rng)
        shard_idx = hash(home_id + str(d)) % shards_per_month
        shards[shard_idx].extend(events)
    for s_idx, rows in enumerate(shards):
      shard_path = out_dir / f"{year:04d}" / f"{month:02d}" / f"events_{year:04d}_{month:02d}_{s_idx:02d}.parquet"
      write_events_parquet(rows, str(shard_path), "1.0.0", s_idx)
    meta_counts["months"][f"{year:04d}-{month:02d}"] = sum(len(s) for s in shards)
  labels = [synth_labels({**h, "year": year}, {}, rng) for h in homes]
  labels_path = out_dir / f"{year:04d}" / "labels.json"
  labels_path.parent.mkdir(parents=True, exist_ok=True)
  labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
  entity_registry = {k: v["entities"] for k, v in registry.items()}
  device_registry = {k: v["devices"] for k, v in registry.items()}
  entity_path = out_dir / f"{year:04d}" / "entity_registry.json"
  device_path = out_dir / f"{year:04d}" / "device_registry.json"
  entity_path.write_text(json.dumps(entity_registry, indent=2), encoding="utf-8")
  device_path.write_text(json.dumps(device_registry, indent=2), encoding="utf-8")
  manifest_path = out_dir / f"{year:04d}" / "manifest.json"
  write_manifest(str(manifest_path), meta_counts)
  click.echo(f"Done. Wrote dataset to {out_dir}")


if __name__ == "__main__":
  main()
