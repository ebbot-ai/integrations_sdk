test:
	uv run pytest

check:
	uv run ruff check
	uv run ruff format
