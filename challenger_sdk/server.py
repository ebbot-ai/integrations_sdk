import importlib
import inspect
import logging
import pkgutil
from types import ModuleType
import typing
from challenger_sdk.component import (
    Actions,
    ChatHistory,
    CompanyEnv,
    EbbotArgument,
    EbbotComponent,
)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationInfo, field_validator

from challenger_sdk.ebbot import Bot, Chat, Company, Message, User


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


class EbbotArguments(typing.TypedDict, total=False):
    message: Message
    bot: Bot
    user: User
    chat_history: ChatHistory
    company: Company
    chat: Chat


class ComponentResponse(BaseModel):
    name: str
    ebbotArguments: list[EbbotArgument]
    description: str
    secrets: list[str]
    env: list[str]
    toolSchema: dict[str, typing.Any]


class ToolCallResult(BaseModel):
    result: typing.Any
    actions: typing.Optional[Actions] = None


def start_server(path, title="Challenger sdk server"):
    logger = logging.getLogger("uvicorn.error")
    fns = walk_package(path)
    app = FastAPI(title=title)

    class ToolCall(BaseModel):
        name: str
        ebbot_data: EbbotArguments
        llm_arguments: dict[str, typing.Any]
        secrets: dict[str, str]
        env: dict[str, str]

        @field_validator("name", mode="after")
        @classmethod
        def valid_name(cls, value: str):
            if value in fns:
                return value
            raise ValueError(f"The tool '{value}' does not exist.")

        @field_validator("secrets", mode="after")
        @classmethod
        def valid_secrets(cls, value: dict[str, str], info: ValidationInfo):
            tool_name = info.data.get("name")
            if not tool_name:
                raise ValueError("Name not valid")

            required_secrets = fns[tool_name].secrets
            for key in value:
                if key not in required_secrets:
                    raise ValueError(
                        f"The secret '{key}' is not valid for tool '{tool_name}'."
                    )
            for secret in required_secrets:
                if secret not in value:
                    raise ValueError(
                        f"Missing required secret '{secret}' for tool '{tool_name}'."
                    )
            return value

        @field_validator("env", mode="after")
        @classmethod
        def valid_env(cls, value: dict[str, str], info: ValidationInfo):
            tool_name = info.data.get("name")
            if not tool_name:
                raise ValueError("Name not valid")

            required_env = fns[tool_name].env
            for env_value in value:
                if env_value not in required_env:
                    raise ValueError(
                        f"The env '{env_value}' is not valid for tool '{tool_name}'."
                    )
            for env_value in required_env:
                if env_value not in value:
                    raise ValueError(
                        f"Missing required env '{env_value}' for tool '{tool_name}'."
                    )
            return value

        @field_validator("llm_arguments", mode="after")
        @classmethod
        def valid_llm_arguments(cls, value: dict[str, typing.Any], info):
            tool_name = info.data.get("name")
            allowed = fns[tool_name].llm_arguments
            for arg in value:
                if arg not in allowed:
                    raise ValueError(
                        f"The llm_argument '{arg}' is not valid for tool '{tool_name}'."
                    )
            return value

    @app.get("/components")
    def list_fns() -> list[ComponentResponse]:
        components = []
        for comp in fns.values():
            components.append(
                ComponentResponse(
                    **{
                        "name": comp.name,
                        "toolSchema": comp.llm_schema(),
                        "description": comp.description,
                        "ebbotArguments": comp.ebbot_arguments,
                        "env": comp.env,
                        "secrets": comp.secrets,
                    }
                )
            )
        return components

    @app.post("/call")
    def call_tool(tool: ToolCall) -> ToolCallResult:
        component = fns[tool.name]
        sig = inspect.signature(component.call)
        extra_args = {}
        if "env" in sig.parameters:
            extra_args["env"] = CompanyEnv(tool.env, tool.secrets)

        logger.info(f"Calling tool {tool.name}")
        result = component.call(**extra_args, **tool.ebbot_data, **tool.llm_arguments)
        return ToolCallResult(**result)

    return app
