from typing import Type, TypeVar, Protocol
import importlib
import pkgutil
from types import ModuleType
import typing
from challenger_sdk.actions import action_endpoints
from challenger_sdk.component import (
    EbbotComponent,
)
from fastapi import FastAPI
from pydantic import BaseModel

from challenger_sdk.connection import EmptyOptions, connection_endpoint
from challenger_sdk.manifest import create_manifest
from challenger_sdk.tools import tool_endpoints
from challenger_sdk.triggers import Trigger, register_triggers, subscription_endpoint


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
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        for comp in list_funcs_in_module(mod, type):
            collected[comp.name] = comp
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
):
    fns = _walk_package(path, EbbotComponent)
    triggers = _walk_package(path, Trigger)
    app = FastAPI(title=title)
    tool_endpoints(app, fns)
    connection_endpoint(app, storage_server_url, storage_server_key, options, secrets)
    action_endpoints(app, storage_server_url, storage_server_key, list(fns.values()))
    if len(triggers) > 0:
        register_triggers(
            app, storage_server_url, storage_server_key, list(triggers.values())
        )
        subscription_endpoint(
            app, storage_server_url, storage_server_key, list(triggers.values())
        )

    @app.get("/manifest")
    def get_manifest():
        return create_manifest(
            list(fns.values()), list(triggers.values()), options, secrets
        )

    return app
