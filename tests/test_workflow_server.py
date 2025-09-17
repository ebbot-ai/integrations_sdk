from fastapi.testclient import TestClient
from pydantic import BaseModel
import responses

from challenger_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


key = "hpM9ZHBvrxlly61irrdoGmnYmdPX5K883eyXtp1jc7vmiowV29tqAJuodLr1uBgD"

app = start_workflow_server(
    "fns",
    "http://localhost:9000",
    key,
    Options,
    Secrets,
)
client = TestClient(app)
json_body = {"options": {"notSecret": "asdf"}, "secrets": {"secret": "asdfasdf"}}


def test_workflow_server_validation():
    response = client.post(
        "/connections",
        json={"options": {"notSecrett": "asdf"}, "secrets": {"secret": "asdfasdf"}},
    )
    assert response.status_code == 422
    response = client.post(
        "/connections",
        json={"options": {"notSecret": "asdf"}, "secrets": {"secrett": "asdfasdf"}},
    )
    assert response.status_code == 422


@responses.activate
def test_workflow_server_connection():

    responses.post(
        url="http://localhost:9000/connections",
        status=201,
        match=[
            responses.matchers.json_params_matcher(json_body),
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={
            **json_body,
            "id": "someid",
            "wfServerId": "ugh",
            "createdAt": "asdf",
            "updatedAt": "asdf",
        },
    )

    response = client.post("/connections", json=json_body)
    assert response.status_code == 201


@responses.activate
def test_action_endpoint():
    responses.get(
        url="http://localhost:9000/connections/someid",
        status=200,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={
            **json_body,
            "id": "someid",
            "wfServerId": "ugh",
            "createdAt": "asdf",
            "updatedAt": "asdf",
        },
    )

    result = client.post(
        "connections/someid/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["secret"] == "asdfasdf"
    assert data["notSecret"] == "asdf"


@responses.activate
def test_action_endpoint_missing_connection():
    responses.get(
        url="http://localhost:9000/connections/someid",
        status=404,
    )
    result = client.post(
        "connections/someid/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 404
