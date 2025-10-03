from typing import (
    Optional,
    Type,
    TypedDict,
    Literal,
    List,
    Dict,
    Any,
)

from pydantic import BaseModel

from challenger_sdk.component import EbbotComponent
from challenger_sdk.triggers import Callback, Trigger

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
    result: Optional[JSONSchema]
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
    installInstructions: Optional[str]


class Manifest(TypedDict):
    triggers: list[TriggerDefinition]
    actions: list[ActionDefinition]
    connection: Optional[JSONSchema]
    subscription: Optional[JSONSchema]
    installInstructions: Optional[str]


def create_manifest(
    components: list[EbbotComponent],
    triggers: list[Trigger],
    optionsType: Optional[Type[BaseModel]] = None,
    secretsType: Optional[Type[BaseModel]] = None,
    installInstructions: Optional[str] = None,
) -> Manifest:
    return Manifest(
        triggers=trigger_definitions(triggers),
        actions=actions_from_components(components),
        connection=connection_schema(optionsType, secretsType),
        subscription=subscription_schema(triggers),
        installInstructions=installInstructions,
    )


def subscription_schema(triggers: list[Trigger]):
    if len(triggers) == 0:
        return None

    class Subscription(BaseModel):
        triggerName: str
        callback: Callback

    return Subscription.model_json_schema()


def connection_schema(
    optionsType: Optional[Type[BaseModel]] = None,
    secretsType: Optional[Type[BaseModel]] = None,
):
    def base():
        return {"type": "object", "properties": {}, "required": []}
    schema = base()
    schema["properties"]["options"] = (
        optionsType.model_json_schema() if optionsType else base()
    )
    schema["required"].append("options")
    schema["properties"]["secrets"] = (
        secretsType.model_json_schema() if secretsType else base()
    )
    schema["required"].append("secrets")
    return schema


def trigger_definitions(triggers: list[Trigger]):
    return [
        TriggerDefinition(
            type="trigger",
            name=trigger.name,
            description=trigger.description,
            schema=_trigger_schema_from_trigger(trigger),
            installInstructions=trigger.installInstructions,
        )
        for trigger in triggers
    ]


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


def _trigger_schema_from_trigger(trigger: Trigger):
    payloadSchema = (
        trigger.result.model_json_schema()
        if isinstance(trigger.result, type) and issubclass(trigger.result, BaseModel)
        else trigger.result
    )

    class TriggerSchema(BaseModel):
        id: str
        name: str
        connectionId: str
        subscriptionId: str

    schema = TriggerSchema.model_json_schema()
    schema["properties"]["payload"] = payloadSchema
    return schema


def _action_schema_from_llm_schema(comp: EbbotComponent):
    schema = comp.llm_schema()
    return ActionSchema(
        call=CallSchema(type="function", function=schema["function"]),
        result=comp.result_schema(),
        errors=comp.error_schema(),
    )
