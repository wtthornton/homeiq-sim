.PHONY: install lint test gen validate summarize

install:
	uv pip install -e .
	uv pip install ruff pytest mypy

lint:
	ruff check .

test:
	pytest -q

gen:
	python -m homeiqsim.cli.generate --config examples/config.full.yaml

validate:
	python -m homeiqsim.cli.validate --manifest out/2025/manifest.json

summarize:
	python -m homeiqsim.cli.summarize --manifest out/2025/manifest.json
