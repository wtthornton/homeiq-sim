import json
import sys
from pathlib import Path

import click


@click.command()
@click.option("--manifest", required=True, type=click.Path(exists=True))
def main(manifest):
  m = json.loads(Path(manifest).read_text(encoding="utf-8"))
  months = m.get("months", {})
  if not months:
    click.echo("ERROR: no months found in manifest", err=True)
    sys.exit(1)
  total = sum(months.values())
  click.echo(f"Found {len(months)} months with {total:,} events total")
  if any(v == 0 for v in months.values()):
    click.echo("WARNING: some months contain zero events")
  click.echo("Validation OK")


if __name__ == "__main__":
  main()
