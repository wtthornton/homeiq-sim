from homeiqsim.io.schema import EventRow, RegistryRow


def test_event_schema_roundtrip():
  e = EventRow(ts=1, home_id="h1", entity_id="light.kitchen", domain="light", state="on", attributes=None)
  assert e.home_id == "h1"


def test_registry_schema():
  r = RegistryRow(home_id="h1", entity_id="sensor.temp", domain="sensor", device_id=None, name=None)
  assert r.domain == "sensor"
