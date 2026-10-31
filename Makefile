.PHONY: check format test lint

check: lint test
	uv run ty check leetcode-recommendation/scripts

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .

test:
	uv run pytest
