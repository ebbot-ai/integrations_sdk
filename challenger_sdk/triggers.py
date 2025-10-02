from dataclasses import dataclass, asdict
from inspect import signature
from typing import Callable, Optional, Union, Type, Any
from fastapi import FastAPI
from pydantic import BaseModel, field_validator
from requests import request
from uuid import uuid4

from challenger_sdk.component import FunctionEnv
from challenger_sdk.connection import (
    function_env_from_connection,
)
from challenger_sdk.storage_server import request_headers
from challenger_sdk.workflow import (
    Callback,
    NewSubscription,
    Subscription,
    WorkflowStorage,
)

SchemaType = Union[Type[BaseModel], dict]
GetEnvFn = Callable[[str], FunctionEnv]

ListenerCallback = Callable[[Subscription], Subscription]


class TriggerEvents(BaseModel):
    created_listener: Optional[ListenerCallback] = None
    removed_listener: Optional[ListenerCallback] = None

    def on_created(self, fn):
        self.created_listener = fn

    def on_removed(self, fn):
        self.removed_listener = fn


class Trigger(BaseModel):
    name: str
    description: str
    result: SchemaType
    call: Callable
    env: list[str] = []
    secrets: list[str] = []
    triggerOptionsType: Optional[Type[BaseModel]] = None
    triggerSecretsType: Optional[Type[BaseModel]] = None
    installInstructions: Optional[str] = None
    events: TriggerEvents = TriggerEvents()

    @field_validator("call", mode="after")
    @classmethod
    def check_callable_arguments(cls, value: Callable, info):
        sig = signature(value)
        allowed = set(["getEnv", "app", "dispatch", "events"])

        for param in sig.parameters.values():
            if param.name not in allowed:
                raise ValueError(
                    f"Invalid parameter '{param.name}' in function '{value.__name__}'. Must be one of {sorted(allowed)}"
                )
        return value


def workflow_trigger(
    description: str,
    result: SchemaType,
    connectionEnv: list[str] = [],
    connectionSecrets: list[str] = [],
    triggerOptions: Optional[Type[BaseModel]] = None,
    triggerSecrets: Optional[Type[BaseModel]] = None,
    installInstructions: Optional[str] = None,
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
            installInstructions=installInstructions,
        )

    return decorator


def subscription_endpoint(
    app: FastAPI, storage: WorkflowStorage, triggers: list[Trigger]
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
        saved_subscription = storage.save_subscription(
            connection_id,
            NewSubscription(
                name=subscription.triggerName, callback=subscription.callback
            ),
        )
        trigger = next(
            (t for t in triggers if t.name == subscription.triggerName), None
        )
        if trigger and trigger.events.created_listener:
            try:
                updated_subscription = trigger.events.created_listener(
                    saved_subscription
                )
                return storage.update_subscription(updated_subscription)
            except Exception as e:
                storage.remove_subscription(connection_id, saved_subscription.id)
                raise e
        return saved_subscription


@dataclass
class TriggerData:
    id: str
    name: str
    connectionId: str
    subscriptionId: str
    payload: dict


def activate_trigger(
    storage: WorkflowStorage, auth_key: str, app: FastAPI, trigger: Trigger
):
    sig = signature(trigger.call)

    def dispatch(subscription_id: str, data):
        subscription = storage.get_subscription(subscription_id)
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
    if "events" in sig.parameters:
        extra_args["events"] = trigger.events
    if "app" in sig.parameters:
        extra_args["app"] = app
    if "getEnv" in sig.parameters:

        def get_env(subscription_id: str):
            subscription = storage.get_subscription(subscription_id)

            connection = storage.get_connection(subscription.connectionId)
            function_env = function_env_from_connection(
                trigger.env, trigger.secrets, connection
            )
            if trigger.triggerOptionsType:
                options = trigger.triggerOptionsType(**subscription.options or {})
                function_env.info.update(options.model_dump())
            if trigger.triggerSecretsType:
                secrets = trigger.triggerSecretsType(**subscription.secrets or {})
                function_env.secrets.update(secrets.model_dump())
            return function_env

        extra_args["getEnv"] = get_env
    trigger.call(dispatch, **extra_args)


def register_triggers(
    app: FastAPI, storage: WorkflowStorage, auth_key: str, triggers: list[Trigger]
):
    for trigger in triggers:
        activate_trigger(storage, auth_key, app, trigger)
