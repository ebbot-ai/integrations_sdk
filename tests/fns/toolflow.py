from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel
from challenger_sdk.component import (
    FunctionEnv,
    workflow_action,
    FieldInfo,
)
from challenger_sdk.triggers import (
    GetEnvFn,
    TriggerEvents,
    with_triggers,
    workflow_trigger,
)
from challenger_sdk.workflow import Subscription


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
    secrets=["secret"],
    env=["notSecret"],
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


def info(env: FunctionEnv):
    return {
        "word": FieldInfo(
            label="What a label it is",
            options=[
                (env.info["notSecret"], "Very not secret"),
                (env.secrets["secret"], "Very secret"),
            ],
        )
    }


@workflow_action(
    description="Say one of the selected words",
    result=Result.model_json_schema(),
    secrets=["secret"],
    env=["notSecret"],
    arguments={
        "word": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
    info=info,
)
def say_a_word(word: str) -> dict:
    return Result(result=f"This is the word: {word}").model_dump()


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


class HookDataWithEnv(BaseModel):
    option: str
    secret: str


installInstructions = "Docs on point, README magic"


@workflow_trigger(
    description="Message received",
    result=HookData,
    installInstructions=installInstructions,
)
def hook_trigger(dispatch, app: FastAPI):
    @app.post("/hook-trigger/{subscriptionId}")
    def hook_trigger(subscriptionId: str, data: HookData):
        dispatch(subscriptionId, data)


@workflow_trigger(
    description="env, secrets from connection",
    result=HookDataWithEnv,
    connectionEnv=["notSecret"],
    connectionSecrets=["secret"],
    installInstructions=installInstructions,
)
def hook_trigger_env_secret(dispatch, app: FastAPI, getEnv: GetEnvFn):
    @app.post("/hook-trigger-env-secret/{subscriptionId}")
    def hook_trigger_secret_env(subscriptionId: str):
        env = getEnv(subscriptionId)
        dispatch(
            subscriptionId,
            HookDataWithEnv(option=env.info["notSecret"], secret=env.secrets["secret"]),
        )


class TriggerEnv(BaseModel):
    option: str


class SecretEnv(BaseModel):
    secret: str


@workflow_trigger(
    description="env, secrets from connection",
    result=HookData,
    triggerOptions=TriggerEnv,
    triggerSecrets=SecretEnv,
    installInstructions=installInstructions,
)
def hook_trigger_own_env_secret(dispatch, app: FastAPI, getEnv: GetEnvFn):
    @app.post("/hook-trigger-own-env/{subscriptionId}")
    def hook_trigger_secret_env(subscriptionId: str):
        env = getEnv(subscriptionId)
        dispatch(
            subscriptionId,
            {"option": env.info["option"], "secret": env.secrets["secret"]},
        )


@workflow_trigger(
    description="",
    result=HookData,
    installInstructions=installInstructions,
)
def on_created(dispatch, app: FastAPI, events: TriggerEvents):
    def call_me_on_created(subscription: Subscription):
        subscription.options = {"extra_prop": "Property prop"}
        return subscription

    events.on_created(call_me_on_created)


@workflow_trigger(
    description="",
    result=HookData,
    installInstructions=installInstructions,
)
def on_created_fail(dispatch, app: FastAPI, events: TriggerEvents):
    def call_me_on_created(subscription: Subscription):
        raise Exception("No, not like that")

    events.on_created(call_me_on_created)


@with_triggers(["hook_trigger", "hook_trigger_own_env_secret"])
def triggers(dispatch, getEnv: GetEnvFn, app: FastAPI):
    class Payload(BaseModel):
        type: Literal["hook_trigger", "hook_trigger_secret"]
        messageId: str
        message: str

    @app.post("/multiple-triggers/{subscriptionId}")
    def shared_fn(subscriptionId, payload: Payload):
        if payload.type == "hook_trigger":
            return dispatch(
                subscriptionId,
                HookData(messageId=payload.messageId, message=payload.message),
            )
        env = getEnv(subscriptionId)
        dispatch(
            subscriptionId,
            {"option": env.info["option"], "secret": env.secrets["secret"]},
        )
