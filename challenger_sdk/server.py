import importlib
import pkgutil
from types import ModuleType
import typing
from challenger_sdk.component import (
    EbbotComponent,
)
from fastapi import FastAPI
from pydantic import BaseModel

from challenger_sdk.connection import connection_endpoint
from challenger_sdk.manifest import create_manifest
from challenger_sdk.tools import tool_endpoints


class ComponentCall(BaseModel):
    name: str
    kwargs: dict


def list_funcs_in_module(mod: ModuleType) -> list[EbbotComponent]:
    """Return all functions defined in this module (not built-ins or imports)."""
    funcs = []
    for obj in vars(mod).values():
        if isinstance(obj, EbbotComponent):
            funcs.append(obj)
    return funcs


def walk_package(package_name: str) -> dict[str, EbbotComponent]:
    """
    Walk the package and its subpackages, import each module,
    and collect function and method names.
    """
    collected: dict[str, EbbotComponent] = {}
    pkg = importlib.import_module(package_name)

    # if it's not a package, just list its funcs
    if not hasattr(pkg, "__path__"):
        return {comp.name: comp for comp in list_funcs_in_module(pkg)}
    # include functions in the root package itself
    for comp in list_funcs_in_module(pkg):
        collected[comp.name] = comp

    for _, name, _ in pkgutil.walk_packages(pkg.__path__, package_name + "."):
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        for comp in list_funcs_in_module(mod):
            collected[comp.name] = comp
    return collected


def start_server(path, title="Challenger sdk server"):
    fns = walk_package(path)
    app = FastAPI(title=title)
    tool_endpoints(app, fns)

    return app


def start_workflow_server(
    path: str,
    storage_server_url: str,
    storage_server_key: str,
    options: typing.Optional[typing.Type[BaseModel]] = None,
    secrets: typing.Optional[typing.Type[BaseModel]] = None,
    title="Challenger SDK Workflow server",
):
    fns = walk_package(path)
    app = FastAPI(title=title)
    tool_endpoints(app, fns)
    connection_endpoint(app, storage_server_url, storage_server_key, options, secrets)

    @app.get("/manifest")
    def get_manifest():
        return create_manifest(list(fns.values()), options, secrets)

    return app
