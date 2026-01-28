from dataclasses import dataclass, asdict
from inspect import signature
import logging
from typing import Annotated, Callable, Optional, Union, Type, Any, Generator
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from requests import request
from uuid import uuid4

from challenger_sdk.component import FunctionEnv
from challenger_sdk.connection import (
    EmptyOptions,
    function_env_from_connection,
)
from challenger_sdk.storage_server import request_headers
from challenger_sdk.workflow import (
    Callback,
    NewSubscription,
    Subscription,
    WorkflowStorage,
)

logger = logging.getLogger(__name__)

SchemaType = Union[Type[BaseModel], dict]
GetEnvFn = Callable[[str], FunctionEnv]
GetTriggersEnvFn = Callable[[str, str], FunctionEnv]
GetSubscriptionsFn = Callable[[], Generator[Subscription, None, None]]
GetSubscriptionsByNameFn = Callable[[str], Generator[Subscription, None, None]]
ListenerCallback = Callable[[Subscription], Subscription]
GetPostInstallEnvFn = Callable[[], FunctionEnv]
PostInstallInstructionsCallback = Callable[[Subscription, GetPostInstallEnvFn], str]


class TriggerEvents(BaseModel):
    created_listener: Optional[ListenerCallback] = None
    removed_listener: Optional[ListenerCallback] = None

    def on_created(self, fn: ListenerCallback):
        self.created_listener = fn

    def on_removed(self, fn: ListenerCallback):
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
    postInstallInstructions: Optional[PostInstallInstructionsCallback] = None
    docs: Optional[str] = None
    events: TriggerEvents = TriggerEvents()

    @field_validator("call", mode="after")
    @classmethod
    def check_callable_arguments(cls, value: Callable, info):
        sig = signature(value)
        allowed = set(["getEnv", "app", "dispatch", "events", "getSubscriptions"])

        for param in sig.parameters.values():
            if param.name not in allowed:
                raise ValueError(
                    f"Invalid parameter '{param.name}' in function '{value.__name__}'. Must be one of {sorted(allowed)}"
                )
        return value


class Triggers(BaseModel):
    triggers: list[str]
    call: Callable


def with_triggers(triggers: list[str]):
    def decorator(func: Callable):
        return Triggers(triggers=triggers, call=func)

    return decorator


def workflow_trigger(
    description: str,
    result: SchemaType,
    connectionEnv: list[str] = [],
    connectionSecrets: list[str] = [],
    triggerOptions: Optional[Type[BaseModel]] = EmptyOptions,
    triggerSecrets: Optional[Type[BaseModel]] = EmptyOptions,
    installInstructions: Optional[str] = None,
    postInstallInstructions: Optional[PostInstallInstructionsCallback] = None,
    docs: Optional[str] = None,
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
            postInstallInstructions=postInstallInstructions,
            docs=docs,
        )

    return decorator


def subscription_endpoint(app: FastAPI, storage: WorkflowStorage, trigger: Trigger):
    class SubscriptionData(BaseModel):
        secrets: Annotated[BaseModel, trigger.triggerSecretsType]
        options: Annotated[BaseModel, trigger.triggerOptionsType]

    class Subscription(BaseModel):
        callback: Callback
        data: SubscriptionData

    @app.post(
        "/connections/{connection_id}/subscriptions/" + trigger.name, status_code=201
    )
    def create_subscription(connection_id: str, subscription: Subscription):
        saved_subscription = storage.save_subscription(
            connection_id,
            NewSubscription(
                name=trigger.name,
                callback=subscription.callback,
                options=subscription.data.options.model_dump()
                if subscription.data.options
                else None,
                secrets=subscription.data.secrets.model_dump()
                if subscription.data.secrets
                else None,
            ),
        )
        if trigger.events.created_listener:
            try:
                updated_subscription = trigger.events.created_listener(
                    saved_subscription
                )
                return storage.update_subscription(updated_subscription)
            except Exception as e:
                storage.remove_subscription(connection_id, saved_subscription.id)
                raise e
        return saved_subscription


class SubscriptionData(BaseModel):
    options: Optional[dict[str, Any]] = None


class SubscriptionInfo(Subscription):
    data: SubscriptionData
    postInstallInstructions: str | None = None


class SubscriptionInfoResult(BaseModel):
    total: int
    data: list[SubscriptionInfo]


def subscription_endpoints(
    app: FastAPI, storage: WorkflowStorage, triggers: dict[str, Trigger]
):
    for _, trigger in triggers.items():
        subscription_endpoint(app, storage, trigger)

    @app.get("/connections/{connectionId}/subscriptions")
    def get_connection_subscriptions(
        connectionId: str,
        limit: int = 1000,
        offset: int = 0,
        name: str | None = None,
    ) -> SubscriptionInfoResult:
        subscriptions = storage.get_connection_subscriptions(
            connectionId, limit, offset, name
        )
        filtered: list[SubscriptionInfo] = []

        for subscription in subscriptions.data:
            if subscription.name in triggers:
                info = SubscriptionInfo(
                    **subscription.__dict__,
                    data=SubscriptionData(options=subscription.options),
                )

                def get_sub_env():
                    return _get_env(storage, trigger, subscription.id)

                trigger = triggers[subscription.name]
                if trigger.postInstallInstructions:
                    cb = trigger.postInstallInstructions
                    info.postInstallInstructions = cb(subscription, get_sub_env)
                filtered.append(info)
        return SubscriptionInfoResult(total=subscriptions.total, data=filtered)

    @app.delete(
        "/connections/{connectionId}/subscriptions/{subscriptionId}", status_code=204
    )
    def delete_subscription(connectionId: str, subscriptionId: str):
        storage.remove_subscription(connectionId, subscriptionId)

    @app.get("/connections/{connectionId}/subscriptions/{subscriptionId}")
    def get_subscription(connectionId: str, subscriptionId: str) -> SubscriptionInfo:
        subscription = storage.get_subscription(subscriptionId)

        def get_sub_env():
            return _get_env(storage, trigger, subscription.id)

        if (
            subscription.connectionId != connectionId
            or subscription.name not in triggers
        ):
            raise HTTPException(status_code=404)

        info = SubscriptionInfo(
            **subscription.__dict__, data=SubscriptionData(options=subscription.options)
        )
        trigger = triggers[subscription.name]
        if trigger.postInstallInstructions:
            cb = trigger.postInstallInstructions
            info.postInstallInstructions = cb(subscription, get_sub_env)
        return info


def get_subscriptions(
    storage: WorkflowStorage, name: Optional[str] = None, per_page=1000
):
    total = per_page
    fetched = 0
    while total > fetched:
        subscriptions = storage.get_subscriptions(1000, fetched, name)
        total = subscriptions.total
        for subscription in subscriptions.data:
            yield subscription
        fetched += total


@dataclass
class TriggerData:
    id: str
    name: str
    connectionId: str
    subscriptionId: str
    payload: dict


def _get_env(storage: WorkflowStorage, trigger: Trigger, subscription_id: str):
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


def _create_dispatch_fn(storage: WorkflowStorage, auth_key: str):
    def dispatch(subscription_id: str, data):
        subscription = storage.get_subscription(subscription_id)
        trigger_data = TriggerData(
            str(uuid4()),
            subscription.name,
            subscription.connectionId,
            subscription_id,
            data.model_dump() if isinstance(data, BaseModel) else data,
        )

        response = request(
            subscription.callback.method.capitalize(),
            subscription.callback.url,
            json=asdict(trigger_data),
            headers=request_headers(auth_key),
        )
        if response.status_code >= 400:
            logger.error(
                f"Error firing trigger: {subscription.name} for subscription {subscription.id} (Status code: {response.status_code})"
            )
            raise HTTPException(
                status_code=response.status_code, detail=response.reason
            )

    return dispatch


def activate_trigger(
    storage: WorkflowStorage, auth_key: str, app: FastAPI, trigger: Trigger
):
    sig = signature(trigger.call)
    extra_args: dict[str, Any] = {}
    if "events" in sig.parameters:
        extra_args["events"] = trigger.events
    if "app" in sig.parameters:
        extra_args["app"] = app
    if "getEnv" in sig.parameters:

        def get_env(subscription_id: str):
            return _get_env(storage, trigger, subscription_id)

        extra_args["getEnv"] = get_env
    if "getSubscriptions" in sig.parameters:

        def get_subscriptions_for_trigger():
            return get_subscriptions(storage, name=trigger.name)

        extra_args["getSubscriptions"] = get_subscriptions_for_trigger

    trigger.call(_create_dispatch_fn(storage, auth_key), **extra_args)


def register_triggers(
    app: FastAPI, storage: WorkflowStorage, auth_key: str, triggers: list[Trigger]
):
    for trigger in triggers:
        activate_trigger(storage, auth_key, app, trigger)


class InvalidTriggerException(Exception):
    def __init__(self, triggerName):
        super().__init__(f"Invalid trigger: {triggerName}")


def activate_triggers_handler(
    storage: WorkflowStorage,
    auth_key: str,
    app: FastAPI,
    triggers_handler: Triggers,
    triggers: dict[str, Trigger],
):
    sig = signature(triggers_handler.call)
    for name in triggers_handler.triggers:
        if name not in triggers.keys():
            raise InvalidTriggerException(name)

    extra_args: dict[str, Any] = {}
    if "app" in sig.parameters:
        extra_args["app"] = app
    if "getEnv" in sig.parameters:

        def get_env(subscription_id: str):
            subscription = storage.get_subscription(subscription_id)
            trigger_obj = triggers.get(subscription.name)

            if not trigger_obj:
                raise InvalidTriggerException(subscription.name)
            return _get_env(storage, trigger_obj, subscription_id)

        extra_args["getEnv"] = get_env
    if "getSubscriptions" in sig.parameters:

        def get_subscriptions_fn(name: str):
            return get_subscriptions(storage, name)

        extra_args["getSubscriptions"] = get_subscriptions_fn

    triggers_handler.call(_create_dispatch_fn(storage, auth_key), **extra_args)


def register_triggers_handlers(
    app: FastAPI,
    storage: WorkflowStorage,
    auth_key: str,
    triggers: dict[str, Trigger],
    triggers_handlers: list[Triggers],
):
    for handler in triggers_handlers:
        activate_triggers_handler(storage, auth_key, app, handler, triggers)
