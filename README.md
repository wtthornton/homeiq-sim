# homeiq-sim

Synthetic Home Assistant-style telemetry generator with **profiles**, **regions**, and **seasonality**.

## Quickstart

```bash
uv pip install -e .
python -m homeiqsim.cli.generate --config examples/config.full.yaml
python -m homeiqsim.cli.validate --manifest out/2025/manifest.json
python -m homeiqsim.cli.summarize --manifest out/2025/manifest.json
```

## Outputs

* Parquet shards per month under `out/<year>/`
* `device_registry.parquet`, `entity_registry.parquet`, `labels_YYYY.parquet`
* `manifest.json` (schema version, counts, dataset hash, per-month stats)

## Features

* Profile-aware entity/device targets (Starter/Intermediate/Advanced/Power)
* Regional multipliers (North/South/Arid West/Marine West/East-Midwest)
* Annual daylight & synthetic weather drivers
* Per-domain cadences (motion, templates/stats, energy, cameras/Frigate, trackers)
* Calendar effects (DST, holidays, vacations)
* Fault injection (drops, dupes, OoO, occasional entity_id rename)
