from fastapi import FastAPI
from pydantic import BaseModel
from challenger_sdk.component import FunctionEnv, workflow_action
from challenger_sdk.triggers import workflow_trigger


class Result(BaseModel):
    result: str


class HelloError(BaseModel):
    message: str


@workflow_action(
    description="Say hello.",
    result=Result,
    errors=[HelloError, {"type": "string"}],
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
)
def say_hello(name: str) -> Result:
    return Result(result=f"Hello {name}")


@workflow_action(
    description="Say hello, the good old fashined way",
    result=Result.model_json_schema(),
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
)
def say_hello_without_pydantic(name: str) -> dict:
    return Result(result=f"Hello {name}").model_dump()


class SecretEnvironmentPollution(BaseModel):
    secret: str
    notSecret: str


@workflow_action(
    description="Say hello with secrets and env",
    result=SecretEnvironmentPollution,
    secrets=["secret"],
    env=["notSecret"],
    arguments={
        "password": {
            "required": True,
            "type": "string",
            "description": "The secret password is required to reveal all our secrets.",
        }
    },
)
def say_hello_with_secret_and_env(
    password: str, env: FunctionEnv
) -> SecretEnvironmentPollution:
    if password == "currywurst":
        return SecretEnvironmentPollution(
            secret=env.secrets["secret"], notSecret=env.info["notSecret"]
        )
    else:
        return SecretEnvironmentPollution(secret="Notreally", notSecret="Notreally")


class HookData(BaseModel):
    messageId: str
    message: str


@workflow_trigger(description="Message received", result=HookData)
def hook_trigger(dispatch, app: FastAPI):

    @app.post("/hook-trigger/{subscriptionId}")
    def hook_trigger(subscriptionId: str, data: HookData):
        dispatch(subscriptionId, data)
