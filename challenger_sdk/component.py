from __future__ import annotations
from dataclasses import dataclass
from pydantic import BaseModel, field_validator
import typing
from typing import Callable, NotRequired, Optional, Type
import inspect


from challenger_sdk.ebbot import Bot, Chat, Company, Message, User

ArgumentType = typing.Literal[
    "string",
    "integer",
    "number",
    "null",
    "boolean",
    "object",
    "array",
]


ChatHistory = list[Message]

EbbotArgument = typing.Literal[
    "message", "chat_history", "user", "bot", "company", "chat"
]

expectedTypes = {
    "message": Message,
    "chat_history": ChatHistory,
    "user": User,
    "bot": Bot,
    "company": Company,
    "chat": Chat,
}


def validate(arg: EbbotArgument, param: inspect.Parameter):
    actual = param.annotation
    if actual is not inspect._empty and actual is not expectedTypes[arg]:
        raise ValueError(
            f"Parameter '{arg}' must be annotated as {expectedTypes[arg]}, got {actual}"
        )


class LLMArgument(typing.TypedDict):
    required: bool
    description: str
    type: ArgumentType
    # properties: typing.Optional[str]


LLMArguments = dict[str, LLMArgument]

ResultType = typing.Union[Type[BaseModel], dict]


@dataclass
class CompanyEnv:
    info: dict[str, str]
    secrets: dict[str, str]


FunctionEnv = CompanyEnv


@dataclass
class FieldInfo:
    label: str
    options: Optional[list[tuple[str, str]]] = None
    translations: Optional[dict[str, FieldInfo]] = None


InfoReturnType = dict[str, FieldInfo]
InfoCallback = Callable[[FunctionEnv], InfoReturnType]


class EbbotComponent(BaseModel):
    name: str
    description: str
    ebbot_arguments: list[EbbotArgument]
    llm_arguments: LLMArguments
    call: typing.Callable
    env: list[str] = []
    secrets: list[str] = []
    result: typing.Optional[ResultType] = None
    errors: list[ResultType] = []
    info: typing.Optional[InfoCallback] = None
    displayName: typing.Optional[str] = None

    def llm_schema(self):
        properties: dict[str, typing.Any] = {}
        required: list[str] = []
        for arg_name, arg_schema in self.llm_arguments.items():
            properties[arg_name] = {
                "description": arg_schema["description"],
                "type": arg_schema["type"],
            }
            if arg_schema["required"]:
                required.append(arg_name)

        parameters: dict[str, typing.Any] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }

    def result_schema(self) -> typing.Optional[dict[str, typing.Any]]:
        if not self.result:
            return None
        if isinstance(self.result, type) and issubclass(self.result, BaseModel):
            return self.result.model_json_schema()
        if isinstance(self.result, dict):
            return self.result

    def error_schema(self) -> list[dict[str, typing.Any]]:
        error_schemas = []
        for error in self.errors:
            if isinstance(error, type) and issubclass(error, BaseModel):
                error_schemas.append(error.model_json_schema())
            elif isinstance(error, dict):
                error_schemas.append(error)
        return error_schemas

    @field_validator("call", mode="after")
    @classmethod
    def check_callable_arguments(cls, value: typing.Callable, info):
        sig = inspect.signature(value)
        allowed = (
            set(info.data.get("ebbot_arguments", []))
            | set(info.data.get("llm_arguments", {}).keys())
            | set(["env"])
        )
        for param in sig.parameters.values():
            if param.name not in allowed:
                raise ValueError(
                    f"Invalid parameter '{param.name}' in function '{value.__name__}'. Must be one of {sorted(allowed)}"
                )
        for ebbot_arg in info.data.get("ebbot_arguments", []):
            param = sig.parameters.get(ebbot_arg)
            if not param:
                continue
            validate(ebbot_arg, param)
        return value


class MessageDataDict(typing.TypedDict):
    type: typing.Literal["text"]
    text: str


class MessageResult(typing.TypedDict):
    type: typing.Literal["message"]
    message: MessageDataDict


class PatchUserData(typing.TypedDict, total=False):
    firstName: str
    lastName: str
    email: str


class PatchUserResult(typing.TypedDict):
    type: typing.Literal["patch_user"]
    data: PatchUserData


class StoreResult(typing.TypedDict):
    type: typing.Literal["store"]
    data: dict[str, typing.Any]


class SetTicketCreatedResult(typing.TypedDict):
    type: typing.Literal["set_ticket_created"]
    value: bool


Actions = list[
    typing.Union[MessageResult, PatchUserResult, StoreResult, SetTicketCreatedResult]
]


class ToolResult(typing.TypedDict):
    result: typing.Any
    actions: NotRequired[Actions]


def component(
    description: str,
    ebbot_arguments: list[EbbotArgument] = [],
    llm_arguments: LLMArguments = {},
    env: list[str] = [],
    secrets: list[str] = [],
) -> typing.Callable[[typing.Callable[..., ToolResult]], EbbotComponent]:
    def decorator(func: typing.Callable[..., ToolResult]) -> EbbotComponent:
        return EbbotComponent(
            name=func.__name__,
            description=description,
            ebbot_arguments=ebbot_arguments,
            llm_arguments=llm_arguments,
            secrets=secrets,
            env=env,
            call=func,
        )

    return decorator


def workflow_action(
    description: str,
    result: ResultType,
    errors: list[ResultType] = [],
    env: list[str] = [],
    secrets: list[str] = [],
    arguments: LLMArguments = {},
    info: typing.Optional[InfoCallback] = None,
    display_name: typing.Optional[str] = None,
) -> typing.Callable[[typing.Callable[..., typing.Any]], EbbotComponent]:
    def decorator(func: typing.Callable[..., typing.Any]) -> EbbotComponent:
        return EbbotComponent(
            name=func.__name__,
            description=description,
            ebbot_arguments=[],
            llm_arguments=arguments,
            secrets=secrets,
            env=env,
            call=func,
            result=result,
            errors=errors,
            info=info,
            displayName=display_name,
        )

    return decorator
