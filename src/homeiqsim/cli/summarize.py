import json
from pathlib import Path

import click


@click.command()
@click.option("--manifest", required=True, type=click.Path(exists=True))
def main(manifest):
  m = json.loads(Path(manifest).read_text(encoding="utf-8"))
  months = m.get("months", {})
  rows = sorted(months.items())
  width = max(len(k) for k, _ in rows) if rows else 7
  click.echo("Month".ljust(width) + " | Events")
  click.echo("-" * width + "-|--------")
  for k, v in rows:
    click.echo(k.ljust(width) + f" | {v:,}")
  click.echo(f"Total homes: {m.get('homes')}, Year: {m.get('year')}")


if __name__ == "__main__":
  main()
