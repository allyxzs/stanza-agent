.PHONY: install test lint run-api run-cli docker-build clean

install:
	pip install -e ".[dev]"

test:
	pytest -v --tb=short

lint:
	ruff check src/ tests/

run-api:
	uvicorn stanza.api.server:app --host 0.0.0.0 --port 8000 --reload

run-cli:
	python -m stanza.cli.main info

docker-build:
	docker build -t allyxzs/stanza-agent:3.0.0 .

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
