test:
	uv run pytest

check:
	uv run pyright
	uv run ruff check
	uv run ruff format --check

fix:
	uv run ruff format
	uv run ruff check --fix
