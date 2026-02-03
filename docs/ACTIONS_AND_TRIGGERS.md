# Actions and Triggers

The workflow server discovers actions and triggers from a module (usually named `fns`) and exposes them via the manifest and runtime endpoints.

## Define actions

Workflow actions are functions decorated with `@workflow_action` from `integrations_sdk.component`.

```python
from pydantic import BaseModel, Field
from integrations_sdk.component import FunctionEnv, workflow_action


class Result(BaseModel):
    result: str = Field(description="The end result")


class HelloError(BaseModel):
    message: str


@workflow_action(
    description="Say hello.",
    result=Result,
    errors=[HelloError, {"type": "string"}],
    display_name="Say hello",
    docs="How the say_hello action works",
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name.",
        }
    },
    argument_docs={
        "name": "The name of the person to greet.",
    },
)
def say_hello(name: str) -> Result:
    return Result(result=f"Hello {name}")
```

Key points:
- `description`, `display_name`, `docs`: surfaced in the manifest.
- `arguments`: JSON-schema-like definition for LLM/tool arguments.
- `argument_docs`: additional text for each argument.
- `result`: Pydantic model or JSON schema returned in the manifest.
- `errors`: list of error schemas; Pydantic or raw JSON schema dicts.

If an action needs connection env or secrets, add `env` and `secrets` and accept `FunctionEnv`:

```python
from integrations_sdk.component import FunctionEnv, workflow_action


@workflow_action(
    description="Say hello with secrets and env",
    env=["notSecret"],
    secrets=["secret"],
    arguments={
        "password": {
            "required": True,
            "type": "string",
            "description": "The secret password.",
        }
    },
)
def say_hello_with_secret_and_env(password: str, env: FunctionEnv) -> dict:
    return {"secret": env.secrets["secret"], "notSecret": env.info["notSecret"]}
```

To provide dynamic field metadata for an action, pass `info=` and return `FieldInfo` values:

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


@workflow_action(
    description="Say one of the selected words",
    env=["notSecret"],
    secrets=["secret"],
    arguments={
        "word": {
            "required": True,
            "type": "string",
            "description": "Pick a word.",
        }
    },
    info=info,
)
def say_a_word(word: str) -> dict:
    return {"result": f"This is the word: {word}"}
```

`GET /connections/{id}/form/{action_name}` returns this field metadata.

## Define triggers

Workflow triggers are decorated with `@workflow_trigger` from `integrations_sdk.triggers`. A trigger registers a route and uses `dispatch(subscription_id, payload)` to send data to the engine.

```python
from fastapi import FastAPI
from pydantic import BaseModel
from integrations_sdk.triggers import workflow_trigger


class HookData(BaseModel):
    messageId: str
    message: str


@workflow_trigger(
    description="Message received",
    result=HookData,
    installInstructions="Docs on point, README magic",
    docs="How the hook_trigger trigger works",
)
def hook_trigger(dispatch, app: FastAPI):
    @app.post("/hook-trigger/{subscriptionId}")
    def hook_trigger(subscriptionId: str, data: HookData):
        dispatch(subscriptionId, data)
```

Trigger env/secrets can come from the connection or from the subscription itself:

```python
from pydantic import BaseModel
from integrations_sdk.triggers import GetEnvFn, workflow_trigger


class HookDataWithEnv(BaseModel):
    option: str
    secret: str


@workflow_trigger(
    description="env, secrets from connection",
    result=HookDataWithEnv,
    connectionEnv=["notSecret"],
    connectionSecrets=["secret"],
)
def hook_trigger_env_secret(dispatch, app, getEnv: GetEnvFn):
    @app.post("/hook-trigger-env-secret/{subscriptionId}")
    def hook_trigger_secret_env(subscriptionId: str):
        env = getEnv(subscriptionId)
        dispatch(
            subscriptionId,
            HookDataWithEnv(option=env.info["notSecret"], secret=env.secrets["secret"]),
        )
```

```python
class TriggerEnv(BaseModel):
    option: str


class SecretEnv(BaseModel):
    secret: str


@workflow_trigger(
    description="env, secrets on subscription",
    result=HookDataWithEnv,
    triggerOptions=TriggerEnv,
    triggerSecrets=SecretEnv,
)
def hook_trigger_own_env_secret(dispatch, app, getEnv: GetEnvFn):
    @app.post("/hook-trigger-own-env/{subscriptionId}")
    def hook_trigger_secret_env(subscriptionId: str):
        env = getEnv(subscriptionId)
        dispatch(
            subscriptionId,
            {"option": env.info["option"], "secret": env.secrets["secret"]},
        )
```

## Trigger lifecycle hooks

Use `TriggerEvents` to hook subscription creation.

```python
from integrations_sdk.triggers import TriggerEvents, workflow_trigger
from integrations_sdk.workflow import Subscription


@workflow_trigger(description="", result=HookData)
def on_created(dispatch, app, events: TriggerEvents):
    def call_me_on_created(subscription: Subscription) -> Subscription:
        subscription.options = {"extra_prop": "Property prop"}
        return subscription

    events.on_created(call_me_on_created)
```

If the hook raises an exception, the subscription is rolled back.

## Multiple triggers on one endpoint

Use `with_triggers` when multiple triggers share one route and you want to dispatch by name.

```python
from typing import Literal
from pydantic import BaseModel
from integrations_sdk.triggers import GetEnvFn, GetSubscriptionsByNameFn, with_triggers


@with_triggers(["hook_trigger", "hook_trigger_own_env_secret"])
def triggers(dispatch, getEnv: GetEnvFn, app, getSubscriptions: GetSubscriptionsByNameFn):
    class Payload(BaseModel):
        type: Literal["hook_trigger", "hook_trigger_secret"]
        messageId: str
        message: str

    @app.post("/multiple-triggers")
    def shared_fn(payload: Payload):
        if payload.type == "hook_trigger":
            for subscription in getSubscriptions("hook_trigger"):
                return dispatch(
                    subscription.id,
                    HookData(messageId=payload.messageId, message=payload.message),
                )
        for subscription in getSubscriptions("hook_trigger_own_env_secret"):
            env = getEnv(subscription.id)
            dispatch(
                subscription.id,
                {"option": env.info["option"], "secret": env.secrets["secret"]},
            )
```

## Subscription schemas

When you set `connectionEnv` / `connectionSecrets` or `triggerOptions` / `triggerSecrets`, the trigger’s `subscriptionSchema` is included in the manifest so the engine knows what data is required for installation.
