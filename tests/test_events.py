from datetime import date, datetime, timezone

from homeiqsim.synth.events import synth_day_events


def test_domain_sums_match_total():
  day_ctx = {
    "home_id": "h1",
    "date": date(2025, 1, 1),
    "sunrise": datetime(2025, 1, 1, 7, tzinfo=timezone.utc),
    "sunset": datetime(2025, 1, 1, 17, tzinfo=timezone.utc),
    "region": "north",
    "region_mults": {"lighting_winter_mult": 1.2, "hvac_mult": 1.3},
  }
  ents = {"lights": 20, "thermostats": 2, "sensors": 150}
  def w(_):
    return {"temp_c": 5.0, "rel_humidity": 0.6, "precip": False}
  rows = synth_day_events(day_ctx, ents, {"weather": w}, None)
  assert isinstance(rows, list)
  assert all("home_id" in r for r in rows)
