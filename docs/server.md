# Creating the workflow server

This SDK exposes a workflow server that handles connections, actions, and triggers. The server is built with FastAPI and is created with `start_workflow_server`.


## Create the server

Add the following to a python file, for example in the root of your project:

```python
from pydantic import BaseModel
from integrations_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str

app = start_workflow_server(
    "fns",
    "http://localhost:9000",
    "engine-api-key",
    Options,
    Secrets,
    install_instructions="Docs on point, README magic",
    docs="My docs",
    auth_token="optional-shared-token",
)
```

Arguments:
- `module_name`: module path containing workflow actions and triggers (e.g. `"fns"`).
- `engine_base_url`: base URL for the ebbot workflow engine. You can set this to any url when testing your server.
- `engine_api_key`: bearer token used when the server calls ebbot workflow engine. You can set this to any value when testing.
- `Options`/`Secrets`: Pydantic models describing required connection data.
- `validator`: optional function to validate the `Options` and `Secrets` payload.
- `install_instructions`: This is shown when installing the workflow server. Markdown is allowed.
- `docs`: Provide documentation for this workflow server. This will be added as a documentation page on the ebbot platform docs. Markdown is allowed.
- `auth_token`: optional server auth; if set, requests must include `Authorization: Bearer <token>`.
- `dev_mode`: The ebbot platform takes care of storing options and secrets for you in production. That is not available when testing the server locally, so we provide a dev_mode that stores your information in a local sqlite database. Set this to true when testing your server.

## Setting up the server for development
In this example, actions and triggers that you create will be located in the `fns` folder. Change this to your liking.

When developing and the `engine_base_url` and `engine_api_key` don't matter, you should also set `dev_mode=True` to allow you to store options and secrets locally.

```python
from pydantic import BaseModel
from integrations_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str

app = start_workflow_server(
    "fns",
    "http://localhost:9000", # can be anything
    "engine-api-key", # can be anything
    Options,
    Secrets,
    dev_mode=True # Set to true.
)
```

### Starting the server

You can start the server locally by running the python file you created with the fastapi. for example, if you named the file `main.py`:

```bash
[uv run] fastapi dev endeavour/main.py
```

### What the server exposes

The workflow server exposes a REST API that is used by the ebbot platform to utilize it.
You can check the API by navigating to http://localhost:8000/docs

## What's next?

[Learn more how to work with your server]()
