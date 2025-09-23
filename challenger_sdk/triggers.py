from dataclasses import dataclass, asdict
from inspect import signature
from typing import Callable, Literal, Optional, Union, Type, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from requests import Response, get, post, request
from uuid import uuid4

from challenger_sdk.component import FunctionEnv
from challenger_sdk.connection import (
    StoredConnection,
    function_env_from_connection,
    get_connection,
)
from challenger_sdk.storage_api import request_headers

SchemaType = Union[Type[BaseModel], dict]
GetEnvFn = Callable[[str], FunctionEnv]


class Trigger(BaseModel):
    name: str
    description: str
    result: SchemaType
    call: Callable
    env: list[str] = []
    secrets: list[str] = []
    triggerOptionsType: Optional[Type[BaseModel]] = None
    triggerSecretsType: Optional[Type[BaseModel]] = None

    @field_validator("call", mode="after")
    @classmethod
    def check_callable_arguments(cls, value: Callable, info):
        sig = signature(value)
        allowed = set(["getEnv", "app", "dispatch"])

        for param in sig.parameters.values():
            if param.name not in allowed:
                raise ValueError(
                    f"Invalid parameter '{param.name}' in function '{value.__name__}'. Must be one of {sorted(allowed)}"
                )
        return value


class Callback(BaseModel):
    type: Literal["http"]
    method: Literal["post"]
    url: str


class SaveSubscription(BaseModel):
    callback: Callback
    name: str
    options: Optional[dict[str, Any]] = None
    secrets: Optional[dict[str, Any]] = None


class StoredSubscription(SaveSubscription):
    id: str
    connectionId: str


def workflow_trigger(
    description: str,
    result: SchemaType,
    connectionEnv: list[str] = [],
    connectionSecrets: list[str] = [],
    triggerOptions: Optional[Type[BaseModel]] = None,
    triggerSecrets: Optional[Type[BaseModel]] = None,
):
    def decorator(func: Callable) -> Trigger:
        return Trigger(
            name=func.__name__,
            description=description,
            result=result,
            env=connectionEnv,
            secrets=connectionSecrets,
            call=func,
            triggerOptionsType=triggerOptions,
            triggerSecretsType=triggerSecrets,
        )

    return decorator


def subscription_endpoint(
    app: FastAPI, server_url: str, auth_key: str, triggers: list[Trigger]
):
    class Subscription(BaseModel):
        triggerName: str
        callback: Callback

        @field_validator("triggerName", mode="after")
        @classmethod
        def valid_trigger(cls, val: str):
            if val not in [trigger.name for trigger in triggers]:
                raise ValueError("Invalid trigger name")
            return val

    @app.post("/connections/{connection_id}/subscriptions", status_code=201)
    def create_subscription(connection_id: str, subscription: Subscription):
        return store_subscription(
            server_url,
            auth_key,
            connection_id,
            SaveSubscription(
                name=subscription.triggerName, callback=subscription.callback
            ),
        )


@dataclass
class TriggerData:
    id: str
    name: str
    connectionId: str
    subscriptionId: str
    payload: dict


def activate_trigger(server_url: str, auth_key: str, app: FastAPI, trigger: Trigger):
    sig = signature(trigger.call)

    def dispatch(subscription_id: str, data):
        subscription = get_subscription(server_url, auth_key, subscription_id)
        trigger_data = TriggerData(
            str(uuid4()),
            trigger.name,
            subscription.connectionId,
            subscription_id,
            data.model_dump() if isinstance(data, BaseModel) else data,
        )
        request(
            subscription.callback.method.capitalize(),
            subscription.callback.url,
            json=asdict(trigger_data),
            headers=request_headers(auth_key),
        )

    extra_args: dict[str, Any] = {}
    if "app" in sig.parameters:
        extra_args["app"] = app
    if "getEnv" in sig.parameters:

        def get_env(subscription_id: str):
            subscription = get_subscription(server_url, auth_key, subscription_id)
            connection = get_connection(server_url, auth_key, subscription.connectionId)
            return function_env_from_connection(
                trigger.env, trigger.secrets, connection
            )

        extra_args["getEnv"] = get_env
    trigger.call(dispatch, **extra_args)


def register_triggers(
    app: FastAPI, server_url: str, auth_key: str, triggers: list[Trigger]
):
    for trigger in triggers:
        activate_trigger(server_url, auth_key, app, trigger)


def get_subscription(
    server_url: str, auth_key: str, subscription_id: str
) -> StoredSubscription:
    return _response_handler(
        get(
            f"{server_url}/subscriptions/{subscription_id}",
            headers=request_headers(auth_key),
        )
    )


def store_subscription(
    server_url: str, auth_key: str, connection_id: str, subscription: SaveSubscription
):
    return _response_handler(
        post(
            f"{server_url}/connections/{connection_id}/subscriptions",
            headers=request_headers(auth_key),
            json=subscription.model_dump(),
        )
    )


def _response_handler(result: Response):
    if result.status_code < 300:
        return StoredSubscription(**result.json())
    if result.status_code == 404:
        raise HTTPException(status_code=result.status_code, detail="not found")
    raise Exception(f"Error code: {result.status_code}")
