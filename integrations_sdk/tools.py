import inspect
from typing import Any, Optional, TypedDict
from fastapi import FastAPI
from pydantic import BaseModel, ValidationInfo, field_validator
from integrations_sdk.ebbot import Bot, Chat, Company, Message, User
from integrations_sdk.component import (
    ChatHistory,
    EbbotArgument,
    EbbotComponent,
    Actions,
    FunctionEnv,
)
import logging

logger = logging.getLogger(__name__)


class EbbotArguments(TypedDict, total=False):
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
    toolSchema: dict[str, Any]
    displayName: str | None = None


class ToolCallResult(BaseModel):
    result: Any
    actions: Optional[Actions] = None


def tool_endpoints(app: FastAPI, fns: dict[str, EbbotComponent]):
    class ToolCall(BaseModel):
        name: str
        ebbot_data: EbbotArguments
        llm_arguments: dict[str, Any]
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
        def valid_llm_arguments(cls, value: dict[str, Any], info):
            tool_name = info.data.get("name")
            llm_arguments = fns[tool_name].llm_arguments
            allowed = {}
            if isinstance(llm_arguments, type) and issubclass(llm_arguments, BaseModel):
                allowed = llm_arguments.model_json_schema()["properties"]
            elif isinstance(llm_arguments, dict):
                allowed = llm_arguments
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
                        "displayName": comp.displayName,
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
            extra_args["env"] = FunctionEnv(tool.env, tool.secrets)

        logger.info(f"Calling tool {tool.name}")
        raw = component.call(**extra_args, **tool.ebbot_data, **tool.llm_arguments)
        data = raw.model_dump() if isinstance(raw, BaseModel) else raw
        if component.type == "endeavour":
            return ToolCallResult(**data)
        return ToolCallResult(result=data)
