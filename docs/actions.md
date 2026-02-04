# Actions

Actions are the operations your workflow server exposes to the Ebbot platform. They appear in the
manifest and can be executed at runtime by the Ebbot platform.

## How actions are discovered

The workflow server scans a module (usually named `fns`) for functions decorated with
`@workflow_action`. Each decorated function becomes an action that can be used by
the Ebbot platform.

## Define an action

Actions are regular Python functions with a decorator that provides metadata, schemas, and optional
connection requirements.

```python
from pydantic import BaseModel, Field
from integrations_sdk.component import workflow_action


class Result(BaseModel):
    result: str = Field(description="The end result")


class HelloError(BaseModel):
    message: str

class HelloArguments(BaseModel):
    name: str

@workflow_action(
    description="Say hello.",
    result=Result,
    errors=[HelloError, {"type": "string"}],
    display_name="Say hello",
    docs="How the say_hello action works",
    arguments=HelloArguments,
    argument_docs={
        "name": "The name of the person to greet.",
    },
)
def say_hello(name: str) -> Result:
    return Result(result=f"Hello {name}")
```

Key points:
- `description`, `display_name`, `docs`: surfaced in the manifest for UI/help text.
- `arguments`: JSON-schema-like definition for LLM/tool arguments.
- `argument_docs`: additional per-argument text.
- `result`: Pydantic model or JSON schema returned in the manifest.
- `errors`: list of error schemas; Pydantic or raw JSON schema dicts.

## Action arguments vs. function signature

The SDK validates that `arguments` and the Python function signature match. If you define an
argument in the decorator, you must accept it in the function signature (and vice versa). This
validation keeps the manifest consistent with the runtime execution of the action.

## Using connection env and secrets

Actions often need connection-specific values (non-secret config and secrets). Declare required
values in `env` and `secrets`, and accept a `FunctionEnv` parameter in the function signature.

```python
from integrations_sdk.component import FunctionEnv, workflow_action

class SecretArguments(BaseModel):
    password: str

@workflow_action(
    description="Say hello with secrets and env",
    env=["notSecret"],
    secrets=["secret"],
    arguments=SecretArguments,
)
def say_hello_with_secret_and_env(password: str, env: FunctionEnv) -> dict:
    return {"secret": env.secrets["secret"], "notSecret": env.info["notSecret"]}
```

Notes:
- `FunctionEnv.info` holds non-secret connection values.
- `FunctionEnv.secrets` holds secret values.

## Dynamic field metadata

You can provide dynamic, connection-aware field metadata with `info=`. This is helpful for
populating dropdowns or labels based on the specific connection used.

```python
from integrations_sdk.component import FieldInfo, FunctionEnv, workflow_action


def info(env: FunctionEnv) -> dict:
    return {
        "word": FieldInfo(
            label="What a label it is",
            description="A more detailed description",
            options=[
                (env.info["notSecret"], "Very not secret"),
                (env.secrets["secret"], "Very secret"),
            ],
        )
    }

class WordArguments(BaseModel):
    word: str

@workflow_action(
    description="Say one of the selected words",
    env=["notSecret"],
    secrets=["secret"],
    arguments=WordArguments,
    info=info,
)
def say_a_word(word: str) -> dict:
    return {"result": f"This is the word: {word}"}
```

This information is fetched when rendering the UI for the action, to make it more user-friendly.

## Manifest behavior

Every action appears in the manifest with:
- Its metadata (`description`, `display_name`, `docs`).
- Arguments schema and docs.
- Result and error schemas.

The manifest is how the Ebbot platform discovers which actions are available for a server and how
to call them.

## Runtime execution

When an action is invoked, the workflow server validates the payload against the declared argument
schema and then calls the underlying Python function. If the action declares `env`/`secrets`, the
server resolves the connection and passes a `FunctionEnv` to the action.

If a declared env or secret is missing, the request fails with a validation error rather than
calling the action with incomplete data.
