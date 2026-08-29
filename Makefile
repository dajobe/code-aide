# code-aide quality checks (uv-based)

.PHONY: build install test lint format format-check typecheck hooks check

build:
	uv build

install:
	uv sync

test:
	uv run pytest -n4 -q

lint:
	uv run ruff check .

format:
	uv run black .

format-check:
	uv run black --check .

typecheck:
	uv run mypy

hooks:
	pre-commit install

check: lint format-check typecheck
