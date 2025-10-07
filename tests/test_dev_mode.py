from fastapi.testclient import TestClient
from pydantic import BaseModel

from challenger_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


key = "hpM9ZHBvrxlly61irrdoGmnYmdPX5K883eyXtp1jc7vmiowV29tqAJuodLr1uBgD"

app = start_workflow_server(
    "fns", "http://localhost:9000", key, Options, Secrets, dev_mode=True
)
client = TestClient(app)
json_body = {"options": {"notSecret": "asdf"}, "secrets": {"secret": "asdfasdf"}}


def test_create_connection():
    response = client.post("/connections", json=json_body)
    assert response.status_code == 201
    data = response.json()
    get_response = client.get(f"/connections/{data['id']}")
    assert get_response.status_code == 200


def test_action_endpoint():
    response = client.post("/connections", json=json_body)
    data = response.json()
    result = client.post(
        f"connections/{data['id']}/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["secret"] == "asdfasdf"
    assert data["notSecret"] == "asdf"


def test_action_endpoint_missing_connection():
    result = client.post(
        "connections/a897cef1-f953-44c3-a054-6290503c54a5/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 404


def test_save_subscription():
    response = client.post("/connections", json=json_body)
    data = response.json()
    result = client.post(
        f"connections/{data['id']}/subscriptions/hook_trigger",
        json={
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
            "data": {
                "secrets": {},
                "options": {},
            },
        },
    )
    assert result.status_code == 201
