# Developing your server

This assumes you already [installed the sdk](/installation) and set [things up for development.](/server).

## Set up your connection

You should start with setting up your connection. First, adjust your `Options` and `Secrets` so that
you collect the necessary information for connecting to the external system you want to integrate with.

For example:

```python
from pydantic import BaseModel
from integrations_sdk.server import start_workflow_server


class Options(BaseModel):
    baseUrl: str


class Secrets(BaseModel):
    apiKey: str

app = start_workflow_server(
    "fns",
    "http://localhost:9000",
    "engine-api-key",
    Options,
    Secrets,
    dev_mode=True # Set to true.
)
```

## Test creating your connection

[Start the server](/server#starting-your-server) and go to http://localhost:8000/docs

You will be presented with the API documentation where you can test your server.

Creating a connection is done using the `POST /connections` endpoint:

![Create connection](/images/create_connection.png)

Store the conenction ID you get back and then close the server.

## Adding an action

Let's add an [action](/actions.md) by creating the directorty "fns" and then create the file `fns/actions.py`, and add the following action:

```python
from pydantic import BaseModel, Field
from integrations_sdk.component import workflow_action

class Result(BaseModel):
    result: str

@workflow_action(
    description="Hello world",
    result=Result,
    display_name="Say hello",
    docs="How the say_hello action works",
    arguments={}
)
def say_hello() -> Result:
    return Result(result=f"Hello world!")
```

Restart the server and head to http://localhost:8000/docs again. You will see an new endpoint, `POST /connections/{connection_id/call/say_hello`, go ahead and try it out (with the id of the connection you created in the first step):

![Call action](/images/call_action.png)

## Read more

Check the documentation on [actions](/actions.md) and [triggers](/triggers) to read more
