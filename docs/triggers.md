# Triggers

Triggers let your workflow server notify the Ebbot platform when something happens in the
integrated system. A trigger defines a subscription type in the manifest and registers runtime
routes that dispatch events to the workflow engine.

## How Triggers Are Discovered

The workflow server scans a module (usually named `fns`) for functions decorated with
`@workflow_trigger` from `integrations_sdk.triggers`. Each decorated function becomes a trigger in
the generated manifest.

## Define a Trigger

Triggers register HTTP routes on the FastAPI app and use `dispatch(subscription_id, payload)` to send events to subscribers.

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

Key points:
- `description`, `docs`, and `installInstructions` are surfaced in the manifest.
- `result` is the Pydantic model or JSON schema for the dispatched payload.
- The inner FastAPI route is where you parse inbound events and call `dispatch`.

## Connection Env and Subscription Options

Triggers can read env/secrets from the connection or from the subscription itself. This drives the subscription schema in the manifest and ensures the platform collects the right data at install time.

### Connection Env and Secrets

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

### Subscription Options and Secrets

```python
from pydantic import BaseModel
from integrations_sdk.triggers import GetEnvFn, workflow_trigger


class TriggerEnv(BaseModel):
    option: str


class SecretEnv(BaseModel):
    secret: str


class HookDataWithEnv(BaseModel):
    option: str
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

Notes:
- `connectionEnv` / `connectionSecrets` pull from the connection.
- `triggerOptions` / `triggerSecrets` are collected per subscription.
- `getEnv(subscription_id)` resolves the correct values for that subscription.

## Trigger Lifecycle Hooks

Use `TriggerEvents` to run logic when a subscription is created. This is useful for provisioning remote webhooks or storing derived configuration.

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

If the hook raises an exception, the subscription creation is rolled back.

## Multiple Triggers on One Endpoint

Use `with_triggers` when several triggers share a route and you want to dispatch by trigger name.

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

## Subscription Schemas in the Manifest

When you set `connectionEnv` / `connectionSecrets` or `triggerOptions` / `triggerSecrets`, the trigger's `subscriptionSchema` is included in the manifest so the Ebbot platform knows which values are required to install the subscription.

## Runtime Behavior

At runtime, the workflow server:
- Resolves the subscription by ID.
- Validates incoming payloads with your Pydantic models.
- Dispatches events to the engine for each subscription.

If required env or secrets are missing, dispatching fails with a validation error rather than
sending incomplete data.
