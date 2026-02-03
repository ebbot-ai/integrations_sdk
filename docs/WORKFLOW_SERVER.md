# Workflow Server Setup

This SDK exposes a workflow server that handles connections, actions, and triggers. The server is built with FastAPI and is created with `start_workflow_server`.

## Create the server

```python
from pydantic import BaseModel
from integrations_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


def validator(secrets: Secrets, options: Options) -> None:
    if options.notSecret == secrets.secret:
        raise ValueError("Secret can't be the same as not secret")


app = start_workflow_server(
    "fns",
    "http://localhost:9000",
    "engine-api-key",
    Options,
    Secrets,
    validator=validator,
    install_instructions="Docs on point, README magic",
    docs="My docs",
    auth_token="optional-shared-token",
)
```

Arguments:
- `module_name`: module path containing workflow actions and triggers (e.g. `"fns"`).
- `engine_base_url`: base URL for the workflow engine.
- `engine_api_key`: bearer token used when the server calls the engine.
- `Options`/`Secrets`: Pydantic models describing required connection data.
- `validator`: optional function to validate the `Options` and `Secrets` payload.
- `install_instructions`/`docs`: optional strings surfaced on the manifest.
- `auth_token`: optional server auth; if set, requests must include `Authorization: Bearer <token>`.

## What the server exposes

The workflow server includes routes for:
- `POST /connections` and `GET /connections/{id}`
- `GET /manifest`
- `POST /connections/{id}/call/{action_name}` (action calls)
- `GET /connections/{id}/form/{action_name}` (action field info)
- `POST /connections/{id}/subscriptions/{trigger_name}` and `DELETE /connections/{id}/subscriptions/{subscription_id}`

The server validates request bodies against your `Options` and `Secrets` models and returns `422` when invalid.

## Manifest highlights

`GET /manifest` returns:
- `actions`: all workflow actions defined with `@workflow_action`.
- `triggers`: all workflow triggers defined with `@workflow_trigger`.
- `connection`: schema for `Options` and `Secrets`.
- `installInstructions` and `docs` when provided.

## Auth token behavior

When `auth_token` is set, all routes require a matching bearer token.

```http
Authorization: Bearer optional-shared-token
```

Missing or mismatched tokens return `401`.
