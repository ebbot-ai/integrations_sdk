from typing import Optional, Type, TypeVar, Protocol
import importlib
import pkgutil
from types import ModuleType
import typing
from challenger_sdk.actions import action_endpoints
from challenger_sdk.component import (
    EbbotComponent,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from challenger_sdk.connection import (
    ConnectionValidator,
    EmptyOptions,
    connection_endpoints,
)
from challenger_sdk.dev_server import DevServerWorkflowStorage
from challenger_sdk.manifest import create_manifest
from challenger_sdk.storage_server import StorageServerWorkflowStorage
from challenger_sdk.tools import tool_endpoints
from challenger_sdk.triggers import (
    Trigger,
    Triggers,
    register_triggers,
    register_triggers_handlers,
    subscription_endpoints,
)


class HasName(Protocol):
    name: str


class ComponentCall(BaseModel):
    name: str
    kwargs: dict


T = TypeVar("T", bound=HasName)


def list_funcs_in_module(mod: ModuleType, cls_type: Type[T]) -> list[T]:
    """Return all items of the given type defined in this module."""
    funcs: list[T] = []
    for obj in vars(mod).values():
        if isinstance(obj, cls_type):
            funcs.append(obj)
    return funcs


def _walk_package(package_name: str, type: Type[T]) -> dict[str, T]:
    """
    Walk the package and its subpackages, import each module,
    and collect function and method names.
    """
    collected: dict[str, T] = {}
    pkg = importlib.import_module(package_name)

    # if it's not a package, just list its funcs
    if not hasattr(pkg, "__path__"):
        return {comp.name: comp for comp in list_funcs_in_module(pkg, type)}
    # include functions in the root package itself
    for comp in list_funcs_in_module(pkg, type):
        collected[comp.name] = comp

    for _, name, _ in pkgutil.walk_packages(pkg.__path__, package_name + "."):
        mod = importlib.import_module(name)
        for comp in list_funcs_in_module(mod, type):
            collected[comp.name] = comp
    return collected


def _walk_package_multiple_trigger_handlers(package_name: str) -> dict[str, Triggers]:
    """Walk a package and gather all Triggers instances mapping each trigger name to its handler object.

    If a Triggers instance lists multiple trigger names, each name will map
    to the same Triggers object. Later instances with the same trigger name
    override earlier ones (mirrors _walk_package behavior).
    """
    collected: dict[str, Triggers] = {}
    pkg = importlib.import_module(package_name)

    def add_triggers(mod):
        for obj in vars(mod).values():
            if isinstance(obj, Triggers):
                for trig_name in obj.triggers:
                    collected[trig_name] = obj

    if not hasattr(pkg, "__path__"):
        add_triggers(pkg)
        return collected

    add_triggers(pkg)
    for _, name, _ in pkgutil.walk_packages(pkg.__path__, package_name + "."):
        mod = importlib.import_module(name)
        add_triggers(mod)
    return collected


def start_server(path, title="Challenger sdk server"):
    fns = _walk_package(path, EbbotComponent)
    app = FastAPI(title=title)
    tool_endpoints(app, fns)

    return app


def start_workflow_server(
    path: str,
    storage_server_url: str,
    storage_server_key: str,
    options: typing.Optional[typing.Type[BaseModel]] = EmptyOptions,
    secrets: typing.Optional[typing.Type[BaseModel]] = EmptyOptions,
    title="Challenger SDK Workflow server",
    dev_mode: bool = False,
    install_instructions: Optional[str] = None,
    validator: Optional[ConnectionValidator] = None,
    auth_token: Optional[str] = None,
):
    if dev_mode:
        storage = DevServerWorkflowStorage()
    else:
        storage = StorageServerWorkflowStorage(storage_server_url, storage_server_key)
    fns = _walk_package(path, EbbotComponent)
    triggers = _walk_package(path, Trigger)
    triggers_handlers = _walk_package_multiple_trigger_handlers(path)
    app = FastAPI(title=title)

    if auth_token:

        @app.middleware("http")
        async def _auth_middleware(request: Request, call_next):
            auth_header = request.headers.get("Authorization")
            expected = f"Bearer {auth_token}"
            if auth_header != expected:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

    tool_endpoints(app, fns)
    connection_endpoints(app, storage, options, secrets, validator)
    action_endpoints(app, storage, list(fns.values()))

    if len(triggers) > 0:
        register_triggers(app, storage, storage_server_key, list(triggers.values()))
        subscription_endpoints(app, storage, triggers)
    if len(triggers_handlers.values()) > 0:
        register_triggers_handlers(
            app, storage, storage_server_key, triggers, list(triggers_handlers.values())
        )

    @app.get("/manifest")
    def get_manifest():
        return create_manifest(
            list(fns.values()),
            list(triggers.values()),
            options,
            secrets,
            install_instructions,
        )

    return app
