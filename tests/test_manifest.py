from fastapi.testclient import TestClient
from pydantic import BaseModel

from challenger_sdk.server import start_workflow_server
from tests.test_server import get_component


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


installInstructions = "Docs on point, README magic"
docs = "My docs"
app = start_workflow_server(
    "fns",
    "http://server.com",
    "key",
    Options,
    Secrets,
    install_instructions=installInstructions,
    docs=docs
)
client = TestClient(app)


def test_manifest_data():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["installInstructions"] == installInstructions
    assert data["docs"] == docs

    component = data["actions"][0]

    assert component["name"] == "store_favorite_food"
    assert (
        component["description"]
        == "The user wants to tell you about their favorite food."
    )
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
    assert hello_component and hello_component["docs"] == "How the say_hello action works"
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
