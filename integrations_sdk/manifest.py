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

from integrations_sdk.component import EbbotComponent
from integrations_sdk.triggers import Callback, Trigger

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


class ActionDefinition(TypedDict, total=False):
    type: Literal["action"]
    name: str
    description: str
    schema: ActionSchema
    displayName: Optional[str]
    docs: Optional[str]
    argumentDocs: Optional[Dict[str, str]]


class TriggerDefinition(TypedDict):
    type: Literal["trigger"]
    name: str
    description: str
    schema: JSONSchema
    subscriptionSchema: JSONSchema
    installInstructions: Optional[str]
    docs: Optional[str]


class Manifest(TypedDict):
    triggers: list[TriggerDefinition]
    actions: list[ActionDefinition]
    connection: Optional[JSONSchema]
    installInstructions: Optional[str]
    apiRateLimitInfo: Optional[str]
    requiredPermissions: Optional[str]
    docs: Optional[str]
    email: Optional[str]
    author: Optional[str]
    url: Optional[str]


def create_manifest(
    components: list[EbbotComponent],
    triggers: list[Trigger],
    optionsType: Optional[Type[BaseModel]] = None,
    secretsType: Optional[Type[BaseModel]] = None,
    installInstructions: Optional[str] = None,
    apiRateLimitInfo: Optional[str] = None,
    requiredPermissions: Optional[str] = None,
    docs: Optional[str] = None,
    email: Optional[str] = None,
    author: Optional[str] = None,
    url: Optional[str] = None,
) -> Manifest:
    return Manifest(
        triggers=trigger_definitions(triggers),
        actions=actions_from_components(components),
        connection=connection_schema(optionsType, secretsType),
        installInstructions=installInstructions,
        apiRateLimitInfo=apiRateLimitInfo,
        requiredPermissions=requiredPermissions,
        docs=docs,
        email=email,
        author=author,
        url=url,
    )


def subscription_schema(triggers: list[Trigger]):
    if len(triggers) == 0:
        return None

    class Subscription(BaseModel):
        triggerName: str
        callback: Callback

    return _normalized_model_schema(Subscription)


def connection_schema(
    optionsType: Optional[Type[BaseModel]] = None,
    secretsType: Optional[Type[BaseModel]] = None,
):
    schema = _schema_base()
    schema["properties"]["options"] = (
        _normalized_model_schema(optionsType) if optionsType else _schema_base()
    )
    schema["required"].append("options")
    schema["properties"]["secrets"] = (
        _normalized_model_schema(secretsType) if secretsType else _schema_base()
    )
    schema["required"].append("secrets")
    return schema


def trigger_definitions(triggers: list[Trigger]):
    return [
        TriggerDefinition(
            type="trigger",
            name=trigger.name,
            description=trigger.description,
            schema=_trigger_schema(trigger),
            subscriptionSchema=_trigger_subscription_schema(trigger),
            installInstructions=trigger.installInstructions,
            docs=trigger.docs,
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
            displayName=comp.displayName,
            docs=comp.docs,
            argumentDocs=comp.argumentDocs,
        )
        for comp in components
        if len(comp.ebbot_arguments) == 0
    ]


def _trigger_subscription_schema(trigger: Trigger):
    schema = _schema_base()
    schema["properties"]["callback"] = _normalized_model_schema(Callback)
    schema["properties"]["data"] = _schema_base()
    schema["properties"]["data"]["required"] = ["options", "secrets"]
    schema["properties"]["data"]["properties"]["options"] = (
        _normalized_model_schema(trigger.triggerOptionsType)
        if trigger.triggerOptionsType
        else _schema_base()
    )
    schema["properties"]["data"]["properties"]["secrets"] = (
        _normalized_model_schema(trigger.triggerSecretsType)
        if trigger.triggerSecretsType
        else _schema_base()
    )
    return schema


def _trigger_schema(trigger: Trigger):
    payloadSchema = (
        _normalized_model_schema(trigger.result)
        if isinstance(trigger.result, type) and issubclass(trigger.result, BaseModel)
        else trigger.result
    )

    class TriggerSchema(BaseModel):
        id: str
        name: str
        connectionId: str
        subscriptionId: str

    schema = _normalized_model_schema(TriggerSchema)
    schema["properties"]["payload"] = payloadSchema
    return schema


def _action_schema_from_llm_schema(comp: EbbotComponent):
    schema = comp.llm_schema()
    return ActionSchema(
        call=CallSchema(type="function", function=schema["function"]),
        result=_normalize_json_schema(comp.result_schema()),
        errors=[_normalize_json_schema(error) for error in comp.error_schema()],
    )


def _schema_base():
    return {"type": "object", "properties": {}, "required": []}


def _normalized_model_schema(model: Type[BaseModel]) -> JSONSchema:
    return _normalize_json_schema(model.model_json_schema())


def _normalize_json_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        normalized = {
            key: _normalize_json_schema(value)
            for key, value in schema.items()
            if key != "anyOf"
        }
        any_of = schema.get("anyOf")
        if isinstance(any_of, list):
            non_null_variants = []
            has_null_variant = False
            for variant in any_of:
                normalized_variant = _normalize_json_schema(variant)
                if _is_null_schema(normalized_variant):
                    has_null_variant = True
                else:
                    non_null_variants.append(normalized_variant)

            if has_null_variant:
                if len(non_null_variants) == 1:
                    merged_schema = non_null_variants[0]
                    if isinstance(merged_schema, dict):
                        normalized.update(merged_schema)
                    else:
                        normalized["anyOf"] = non_null_variants
                elif len(non_null_variants) > 1:
                    normalized["anyOf"] = non_null_variants
            else:
                normalized["anyOf"] = non_null_variants
        return normalized

    if isinstance(schema, list):
        return [_normalize_json_schema(item) for item in schema]

    return schema


def _is_null_schema(schema: Any) -> bool:
    return isinstance(schema, dict) and schema.get("type") == "null"
