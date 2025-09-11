from challenger_sdk.ebbot import User
from challenger_sdk.server import start_server
from fastapi.testclient import TestClient

app = start_server("fns")

client = TestClient(app)


def test_get_components():
    response = client.get("/components")
    assert response.status_code == 200
    data = response.json()
    retrieve_user = get_component(data, "retrieve_user")
    assert len(data) == 4
    assert retrieve_user is not None
    assert retrieve_user["ebbotArguments"] == ["user"]
    store_favorite_food = get_component(data, "store_favorite_food")
    assert store_favorite_food is not None
    assert store_favorite_food["toolSchema"]["type"] == "function"
    assert (
        store_favorite_food["toolSchema"]["function"]["name"] == "store_favorite_food"
    )
    assert (
        store_favorite_food["toolSchema"]["function"]["description"]
        == "The user wants to tell you about their favorite food."
    )
    assert store_favorite_food["toolSchema"]["function"]["parameters"]["properties"][
        "dish"
    ] == {
        "description": "The users favorite food.",
        "type": "string",
    }
    assert get_component(data, "update_user") != None


def test_call_component_ebbot_args():
    userData = User("asdf", "asdf@asdf.com").__dict__
    response = client.post(
        "/call",
        json={
            "name": "retrieve_user",
            "ebbot_data": {"user": userData},
            "llm_arguments": {},
            "secrets": {},
            "env": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"result": userData, "actions": None}


def test_call_component_llm_args():
    response = client.post(
        "/call",
        json={
            "name": "store_favorite_food",
            "ebbot_data": {},
            "llm_arguments": {"dish": "Spaghetti"},
            "secrets": {},
            "env": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "result": "Food recorded!",
        "actions": [
            {
                "type": "store",
                "data": {"dish": "Spaghetti"},
            }
        ],
    }


def test_call_workflow_action():
    response = client.post(
        "/call",
        json={
            "name": "say_hello",
            "ebbot_data": {},
            "llm_arguments": {"name": "Spaghetti"},
            "secrets": {},
            "env": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "actions": None,
        "result": "Hello Spaghetti",
    }


def test_manifest_data():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
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


def test_manifest_result_data():
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


def test_manifest_exclude_ebbot():
    response = client.get(
        "/manifest",
    )
    assert response.status_code == 200
    data = response.json()
    # Update user requires ebbot arguments and should not be included.
    assert get_component(data["actions"], "retrieve_user") == None


def get_component(data: list[dict], name: str) -> dict | None:
    return next((component for component in data if component["name"] == name), None)
