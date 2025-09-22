from uuid import uuid4
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
        url="http://localhost:9000/connections/a897cef1-f953-44c3-a054-6290503c54a5",
        status=404,
    )
    result = client.post(
        "connections/a897cef1-f953-44c3-a054-6290503c54a5/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 404


@responses.activate
def test_save_subscription():
    responses.post(
        url="http://localhost:9000/connections/a897cef1-f953-44c3-a054-6290503c54a5/subscriptions",
        status=201,
        match=[
            responses.matchers.json_params_matcher(
                {
                    "name": "hook_trigger",
                    "callback": {
                        "type": "http",
                        "method": "post",
                        "url": "http://v8-engine.com/called",
                    },
                    "options": None,
                    "secrets": None,
                }
            ),
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={
            "id": str(uuid4()),
            "name": "hook_trigger",
            "connectionId": "a897cef1-f953-44c3-a054-6290503c54a5",
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
            "options": {},
        },
    )

    result = client.post(
        "connections/a897cef1-f953-44c3-a054-6290503c54a5/subscriptions",
        json={
            "triggerName": "hook_trigger",
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
        },
    )
    assert result.status_code == 201


def test_save_subscription_invalid_trigger():
    result = client.post(
        "connections/a897cef1-f953-44c3-a054-6290503c54a5/subscriptions",
        json={
            "triggerName": "no_trigger",
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
        },
    )
    assert result.status_code == 422


@responses.activate
def test_trigger_subscription():
    body = {"messageId": "myid", "message": "This is my message"}
    responses.get(
        url="http://localhost:9000/subscriptions/0008b509-eaba-419a-9012-376797517de5",
        json={
            "id": "0008b509-eaba-419a-9012-376797517de5",
            "connectionId": "a897cef1-f953-44c3-a054-6290503c54a5",
            "name": "hook_trigger",
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
        },
        status=200,
    )

    res = responses.post(
        url="http://v8-engine.com/called",
        status=200,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
    )
    trigger = client.post(
        "/hook-trigger/0008b509-eaba-419a-9012-376797517de5", json=body
    )
    assert trigger.status_code == 200
    assert res.call_count == 1
