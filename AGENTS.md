AGENTS GUIDE FOR THIS REPOSITORY

This file is for autonomous / agentic coding tools working in this repo.
Follow the commands and conventions here unless the user explicitly asks
for something different.


BUILD, LINT, TEST

- Python version: use Python 3.13 (see CI and pyproject).
- Package manager / runner: use `uv` from the repo root.

- Install dependencies:
  - `uv sync`

- Run full test suite (preferred):
  - `make test`
  - This runs `uv run pytest`.

- Run a single test file:
  - `uv run pytest tests/test_cli.py`
  - Replace path with the target test file.

- Run a single test by name (node id):
  - `uv run pytest tests/test_server.py::test_get_components`
  - Use `::TestClassName::test_method` for methods inside classes.

- Run tests with quieter output (CI-style):
  - `uv run pytest -q`

- Type checking (Pyright):
  - `make check`
  - or directly: `uv run pyright`

- Linting / formatting (Ruff):
  - Check only: `make check`
    - runs `uv run ruff check`
    - runs `uv run ruff format --check`
  - Auto-fix + format: `make fix`
    - runs `uv run ruff format`
    - runs `uv run ruff check --fix`

- Local dev servers (pattern):
  - The library exposes FastAPI apps via `start_server` and
    `start_workflow_server` in `challenger_sdk.server`.
  - If you need to run an example app, create a small script that
    imports and starts these, then run it with `uv run python script.py`.


PYTHON STYLE AND CONVENTIONS

- Language level:
  - Use modern Python 3.11+ features (e.g. `list[str]`, `|` union types).
  - Prefer standard types over `typing.List` / `typing.Dict` where
    existing code already does so.

- Imports:
  - Standard library imports first, then third-party, then local.
  - Group by section with a blank line between sections.
  - Within each section, keep imports sorted alphabetically when
    editing blocks.
  - Prefer explicit imports over `import *`.

- Formatting:
  - Treat Ruff as the source of truth for style and formatting.
  - Do not hand-wrap lines oddly; follow existing wrapping patterns
    (e.g. in `challenger_sdk/component.py`, `tools.py`, `triggers.py`).
  - Use double quotes or single quotes consistently with nearby code;
    do not churn purely for quote style.

- Typing:
  - Add type hints for all public functions and methods.
  - Use concrete types where possible:
    - `dict[str, str]`, `list[SomeModel]`, not bare `dict` or `list`.
  - When interacting with Pydantic models, prefer
    `.model_dump()` to get dicts.
  - Reuse existing type aliases and TypedDicts, such as:
    - `EbbotArgument`, `LLMArguments`, `ToolResult`, `Actions`,
      `FunctionEnv`, `Trigger`, `Triggers`, etc.

- Data models (Pydantic and dataclasses):
  - For HTTP payloads and configs, prefer `pydantic.BaseModel`.
  - For internal, simple containers, prefer `@dataclasses.dataclass`.
  - Follow existing patterns:
    - Pydantic models with validators (`field_validator`, `model_validator`).
    - Dataclasses for CLI config structures and env structs.

- Naming conventions:
  - Modules: `snake_case`.
  - Functions: `snake_case`.
  - Variables: `snake_case`.
  - Classes and Pydantic models: `PascalCase`.
  - TypedDict and dataclass names: `PascalCase`.
  - Triggers: use descriptive `snake_case` names.
  - Avoid abbreviations unless already established (e.g. `wfServerId`).

- Error handling:
  - For HTTP validation or user input errors inside FastAPI handlers,
    raise `HTTPException` with appropriate status codes (e.g. 422,
    404, 500) matching current patterns in `triggers.py` and
    `actions.py`.
  - For CLI-level failures (e.g. invalid env configuration in
    `challenger_sdk.cli`), raise `Exception` with a clear, user-facing
    message (tests assert on these messages).
  - Use explicit checks and raise early when env or config is missing
    rather than failing later with attribute errors.

- Logging:
  - Use `logging.getLogger(__name__)` at module level when logging.
  - Log key events (e.g. tool calls, trigger dispatch) at `info` level;
    log failures at `error` level.
  - Avoid excessive debug logging in hot paths.


DOMAIN-SPECIFIC PATTERNS

- Components and actions:
  - Use `EbbotComponent` via the `component` and `workflow_action`
    decorators in `challenger_sdk.component`.
  - Ensure `ebbot_arguments` and `llm_arguments` are consistent with
    function signatures; the validator enforces this.
  - Where possible, define result and error schemas using Pydantic
    models so manifest generation stays consistent.

- Triggers and subscriptions:
  - Use `workflow_trigger` and `with_triggers` from
    `challenger_sdk.triggers`.
  - Trigger `call` functions may accept only the allowed parameters
    enforced by validators (`getEnv`, `app`, `dispatch`, `events`,
    `getSubscriptions`). Do not add new names without updating
    validation.
  - When adding post-install instructions or subscription views,
    follow the patterns in the existing tests under `tests/`.

- Connections and env handling:
  - Use `function_env_from_connection` to construct `FunctionEnv`
    from stored connection data.
  - When requiring options or secrets for a connection, list them in
    the `env` and `secrets` fields of triggers or components.
  - Missing env or secrets for a connection should raise `HTTPException`
    with a clear error message (see `_pick_env_vars`).


TESTING CONVENTIONS

- Test framework: `pytest`.
- Tests live under `tests/`.
- Use plain `assert` statements for expectations.
- Use `pytest.raises` for exception assertions.
- Use `responses` and `unittest.mock` for HTTP and side-effect mocking.
- Prefer clear test function names (`test_…`) that describe behavior
  rather than implementation details.


AGENT WORKFLOW GUIDELINES

- Before making changes:
  - Skim related tests under `tests/` and update or add tests when
    changing behavior.
  - Prefer the smallest viable change that satisfies the request.

- After making changes:
  - Run `make check` to validate types, lint, and formatting.
  - Run focused tests (single files or tests) with
    `uv run pytest tests/path_to_test.py`.
  - For broader changes, run the full suite with `make test`.

- Respect existing behavior:
  - Do not relax validation, error messages, or auth checks unless the
    user explicitly asks; many tests depend on exact messages and
    status codes.
