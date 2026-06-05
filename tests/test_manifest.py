from fastapi.testclient import TestClient
from pydantic import BaseModel

from integrations_sdk.component import workflow_action
from integrations_sdk.manifest import create_manifest
from integrations_sdk.server import start_workflow_server
from integrations_sdk.triggers import workflow_trigger
from tests.test_server import get_component


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


installInstructions = "Docs on point, README magic"
apiRateLimitInfo = "100 requests per minute"
docs = "My docs"
requiredPermissions = "contacts:read messages:write"
app = start_workflow_server(
    "fns",
    "http://server.com",
    "key",
    Options,
    Secrets,
    install_instructions=installInstructions,
    api_rate_limit_info=apiRateLimitInfo,
    required_permissions=requiredPermissions,
    docs=docs,
)
client = TestClient(app)


def test_manifest_data():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["installInstructions"] == installInstructions
    assert data["apiRateLimitInfo"] == apiRateLimitInfo
    assert data["requiredPermissions"] == requiredPermissions
    assert data["docs"] == docs

    component = data["actions"][0]

    assert component["name"] == "store_favorite_food"
    assert (
        component["description"]
        == "The user wants to tell you about their favorite food."
    )
    assert "argumentDocs" not in component or component["argumentDocs"] is None
    assert component["schema"]["call"]["type"] == "function"
    call = component["schema"]["call"]["function"]
    assert call["name"] == "store_favorite_food"
    assert (
        call["description"] == "The user wants to tell you about their favorite food."
    )
    assert call["parameters"]["type"] == "object"

    assert call["parameters"]["properties"]["dish"]["type"] == "string"
    assert call["parameters"]["required"] == ["dish"]
    assert data["triggers"][0]["installInstructions"] == installInstructions
    hello_component = get_component(data["actions"], "say_hello")
    assert (
        hello_component and hello_component["docs"] == "How the say_hello action works"
    )
    assert hello_component["argumentDocs"] == {
        "name": "The name of the person to greet.",
    }
    assert data["triggers"][0]["docs"] == "How the hook_trigger trigger works"


def test_manifest_result_schema():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()

    component = get_component(data["actions"], "say_hello")
    assert component is not None
    result = component["schema"]["result"]
    assert result["properties"]["result"]["type"] == "string"
    component = get_component(data["actions"], "say_hello_without_pydantic")
    assert component is not None
    result = component["schema"]["result"]
    assert result["properties"]["result"]["type"] == "string"


def test_manifest_errors_schema():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()

    component = get_component(data["actions"], "say_hello")
    assert component is not None
    errors = component["schema"]["errors"]
    assert errors[0]["type"] == "object"
    assert errors[0]["properties"]["message"]["type"] == "string"
    assert errors[1]["type"] == "string"


def test_manifest_exclude_ebbot():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    # Update user requires ebbot arguments and should not be included.
    assert get_component(data["actions"], "retrieve_user") is None


def test_manifest_component_result_null():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    # Update user requires ebbot arguments and should not be included.
    component = get_component(data["actions"], "store_favorite_food")
    assert component is not None
    assert component["schema"]["result"] is None


def test_manifest_connection():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connection"]["required"] == ["options", "secrets"]
    assert (
        data["connection"]["properties"]["options"]["properties"]["notSecret"]["type"]
        == "string"
    )
    assert (
        data["connection"]["properties"]["secrets"]["properties"]["secret"]["type"]
        == "string"
    )


def test_manifest_trigger_subscription():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["triggers"][0]["subscriptionSchema"] is not None
    assert (
        data["triggers"][2]["subscriptionSchema"]["properties"]["data"]["properties"][
            "options"
        ]["properties"]["option"]
        is not None
    )
    assert (
        data["triggers"][2]["subscriptionSchema"]["properties"]["data"]["properties"][
            "secrets"
        ]["properties"]["secret"]
        is not None
    )


def test_manifest_trigger_without_options_secrets():
    boring_app = start_workflow_server("fns", "http://server.com", "key")
    client = TestClient(boring_app)
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["triggers"][0]["subscriptionSchema"]["properties"]["data"][
        "required"
    ] == ["options", "secrets"]


def test_manifest_optional_fields_are_not_nullable_in_schema():
    class OptionalOptions(BaseModel):
        name: str | None = None

    class OptionalSecrets(BaseModel):
        secret: str | None = None

    class ActionResult(BaseModel):
        value: str | None = None

    class TriggerPayload(BaseModel):
        payload_value: str | None = None

    class TriggerOptions(BaseModel):
        option: str | None = None

    class TriggerSecrets(BaseModel):
        secret: str | None = None

    @workflow_action(
        description="Action with optional result field", result=ActionResult
    )
    def action_with_optional_result() -> ActionResult:
        return ActionResult(value=None)

    @workflow_trigger(
        description="Trigger with optional fields",
        result=TriggerPayload,
        triggerOptions=TriggerOptions,
        triggerSecrets=TriggerSecrets,
    )
    def trigger_with_optional_fields(dispatch):
        return None

    manifest = create_manifest(
        [action_with_optional_result],
        [trigger_with_optional_fields],
        OptionalOptions,
        OptionalSecrets,
    )

    connection = manifest["connection"]
    assert connection is not None

    options_name = connection["properties"]["options"]["properties"]["name"]
    assert options_name["type"] == "string"
    assert "anyOf" not in options_name

    secrets_secret = connection["properties"]["secrets"]["properties"]["secret"]
    assert secrets_secret["type"] == "string"
    assert "anyOf" not in secrets_secret

    action_schema = manifest["actions"][0].get("schema")
    assert action_schema is not None
    action_result = action_schema.get("result")
    assert action_result is not None

    result_value = action_result["properties"]["value"]
    assert result_value["type"] == "string"
    assert "anyOf" not in result_value

    trigger_payload = manifest["triggers"][0]["schema"]["properties"]["payload"][
        "properties"
    ]["payload_value"]
    assert trigger_payload["type"] == "string"
    assert "anyOf" not in trigger_payload

    subscription_option = manifest["triggers"][0]["subscriptionSchema"]["properties"][
        "data"
    ]["properties"]["options"]["properties"]["option"]
    assert subscription_option["type"] == "string"
    assert "anyOf" not in subscription_option

    subscription_secret = manifest["triggers"][0]["subscriptionSchema"]["properties"][
        "data"
    ]["properties"]["secrets"]["properties"]["secret"]
    assert subscription_secret["type"] == "string"
    assert "anyOf" not in subscription_secret


def test_manifest_api_rate_limit_info():
    manifest = create_manifest(
        [], [], installInstructions="Install me", apiRateLimitInfo=apiRateLimitInfo
    )

    assert manifest["installInstructions"] == "Install me"
    assert manifest["apiRateLimitInfo"] == apiRateLimitInfo
