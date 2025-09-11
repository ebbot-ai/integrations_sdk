from typing import Optional, TypedDict, Literal, List, Dict, Any, NotRequired

from challenger_sdk.component import EbbotComponent

JSONSchema = Dict[str, Any]
ActionErrorSchema = Dict[str, Any]


class CallFunction(TypedDict):
    name: str
    description: str
    parameters: JSONSchema


class CallSchema(TypedDict):
    type: Literal["function"]
    function: CallFunction


class ActionSchema(TypedDict, total=False):
    call: CallSchema
    result: JSONSchema
    errors: List[ActionErrorSchema]


class ActionDefinition(TypedDict):
    type: Literal["action"]
    name: str
    description: str
    schema: ActionSchema


class TriggerDefinition(TypedDict):
    type: Literal["trigger"]
    name: str
    description: str
    schema: JSONSchema


class Manifest(TypedDict):
    triggers: list[TriggerDefinition]
    actions: list[ActionDefinition]
    connection: Optional[JSONSchema]
    subscription: Optional[JSONSchema]


def create_manifest(components: list[EbbotComponent]) -> Manifest:
    return Manifest(
        triggers=[],
        actions=actions_from_components(components),
        connection=None,
        subscription=None,
    )


def actions_from_components(components: list[EbbotComponent]) -> list[ActionDefinition]:
    return [
        ActionDefinition(
            type="action",
            name=comp.name,
            description=comp.description,
            schema=_action_schema_from_llm_schema(comp),
        )
        for comp in components
        if len(comp.ebbot_arguments) == 0
    ]


def _action_schema_from_llm_schema(comp: EbbotComponent):
    schema = comp.llm_schema()
    return ActionSchema(
        call=CallSchema(type="function", function=schema["function"]),
        result=comp.result_schema() or {},
        errors=comp.error_schema(),
    )
