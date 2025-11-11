from datetime import datetime, timedelta, timezone
import math, random as pyrandom


def synth_day_events(day_ctx, entities, drivers, rng):
  """
  Generate state changes for a single day using per-domain cadences and multipliers.

  day_ctx: { "home_id", "date", "sunrise", "sunset", "region_mults": {...} }
  drivers: { "weather": callable(ts)->{temp_c,rel_humidity,precip} }
  """
  home_id = day_ctx["home_id"]
  d = day_ctx["date"]
  sunrise, sunset = day_ctx["sunrise"], day_ctx["sunset"]
  start = datetime(d.year, d.month, d.day, 0, 0, tzinfo=timezone.utc)
  end = start + timedelta(days=1)
  t = start
  results = []
  light_mult = day_ctx["region_mults"].get("lighting_winter_mult", 1.0)
  hvac_mult = day_ctx["region_mults"].get("hvac_mult", 1.0)
  rand_uniform = rng.uniform if rng else pyrandom.uniform
  while t < end:
    w = drivers["weather"](t)
    is_dark = not (sunrise <= t <= sunset)
    n_lights = int((entities.get("lights", 0) * (0.002 if is_dark else 0.0007)) * light_mult)
    for _ in range(n_lights):
      results.append({
        "ts": int(t.timestamp() * 1000),
        "home_id": home_id,
        "entity_id": "light.random",
        "domain": "light",
        "state": "on" if rand_uniform(0, 1) > 0.5 else "off",
        "attributes": None,
      })
    cdd = max(0.0, w["temp_c"] - 22.0)
    hdd = max(0.0, 20.0 - w["temp_c"])
    hvac_rate = (0.02 * cdd + 0.03 * hdd) * hvac_mult
    n_hvac = int(entities.get("thermostats", 0) * hvac_rate)
    for _ in range(n_hvac):
      results.append({
        "ts": int(t.timestamp() * 1000),
        "home_id": home_id,
        "entity_id": "climate.random",
        "domain": "climate",
        "state": "heat" if hdd > cdd else "cool",
        "attributes": {"setpoint": 21.0 if hdd > cdd else 24.0},
      })
    n_templates = int(entities.get("sensors", 0) * 0.0025)
    for _ in range(n_templates):
      results.append({
        "ts": int(t.timestamp() * 1000),
        "home_id": home_id,
        "entity_id": "sensor.template_random",
        "domain": "sensor",
        "state": None,
        "attributes": {"updated": True},
      })
    t += timedelta(minutes=5)
  return results
