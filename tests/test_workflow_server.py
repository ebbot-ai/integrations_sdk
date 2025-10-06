from fastapi.testclient import TestClient
from pydantic import BaseModel
import responses
from pytest import raises
import json
import mocks
from challenger_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


def validator(secrets, options):
    if options.notSecret == secrets.secret:
        raise ValueError("Secret can't be the same as not secret")


app = start_workflow_server(
    "fns", "http://localhost:9000", mocks.key, Options, Secrets, validator=validator
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
    id = mocks.id()
    mocks.post_connection(id)
    mocks.get_connection(id)
    response = client.post("/connections", json=json_body)
    assert response.status_code == 201
    data = response.json()
    get_response = client.get(f"/connections/{data['id']}")
    assert get_response.status_code == 200


@responses.activate
def test_workflow_server_connection_no_options():
    empty_body = {"options": {}, "secrets": {}}
    testApp = start_workflow_server(
        "fns",
        "http://localhost:9000",
        mocks.key,
    )
    client = TestClient(testApp)
    mocks.post_connection(mocks.id(), empty_body)
    response = client.post("/connections", json=empty_body)
    assert response.status_code == 201


@responses.activate
def test_workflow_server_connection_validation():
    invalid_body = {"options": {"notSecret": "secret"}, "secrets": {"secret": "secret"}}
    id = mocks.id()
    mocks.post_connection(id)
    mocks.get_connection(id)
    response = client.post("/connections", json=invalid_body)
    assert response.status_code == 422


@responses.activate
def test_action_endpoint():
    id = mocks.id()
    mocks.get_connection(id)

    result = client.post(
        f"connections/{id}/call/say_hello_with_secret_and_env",
        json={"password": "currywurst"},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["secret"] == "asdfasdf"
    assert data["notSecret"] == "asdf"


@responses.activate
def test_action_info_endpoint():
    id = mocks.id()
    mocks.get_connection(id)
    result = client.get(
        f"connections/{id}/form/say_a_word",
    )
    assert result.status_code == 200
    data = result.json()
    assert data["word"]["label"] == "What a label it is"
    assert data["word"]["options"][0] == ["asdf", "Very not secret"]
    assert data["word"]["options"][1] == ["asdfasdf", "Very secret"]


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
    connectionId = mocks.id()
    mocks.post_subscription(connectionId, mocks.id())

    result = client.post(
        f"connections/{connectionId}/subscriptions/hook_trigger",
        json={
            "options": {},
            "secrets": {},
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
        },
    )
    assert result.status_code == 201


@responses.activate
def test_save_subscription_trigger_created():
    connectionId = mocks.id()
    subId = mocks.id()
    data = {**mocks.default_subscription_data, "name": "on_created"}
    mocks.post_subscription(connectionId, subId, data)
    patch_response = mocks.patch_subscription(connectionId, subId, data)
    result = client.post(
        f"connections/{connectionId}/subscriptions/on_created",
        json={
            "options": {},
            "secrets": {},
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
        },
    )

    assert result.status_code == 201
    assert patch_response.call_count == 1
    assert patch_response.calls[0].request.body is not None
    response_data = json.loads(patch_response.calls[0].request.body)
    assert response_data["options"]["extra_prop"] == "Property prop"


@responses.activate
def test_save_subscription_trigger_created_rollback():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    json_data = {
        "name": "on_created_fail",
        "callback": {
            "type": "http",
            "method": "post",
            "url": "http://v8-engine.com/called",
        },
        "options": {},
        "secrets": {},
    }
    mocks.post_subscription(connectionId, subscriptionId, json_data)
    remove_req = mocks.delete_subscription(connectionId, subscriptionId)

    with raises(Exception):
        client.post(
            f"connections/{connectionId}/subscriptions/on_created_fail",
            json={
                "triggerName": "on_created_fail",
                "callback": {
                    "type": "http",
                    "method": "post",
                    "url": "http://v8-engine.com/called",
                },
                "options": {},
                "secrets": {},
            },
        )
    assert remove_req.call_count == 1


@responses.activate
def test_save_subscription_trigger_env_secrets():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    json_data = {
        "name": "hook_trigger_own_env_secret",
        "callback": {
            "type": "http",
            "method": "post",
            "url": "http://v8-engine.com/called",
        },
        "options": {"option": "opt"},
        "secrets": {"secret": "secretopt"},
    }
    mocks.post_subscription(connectionId, subscriptionId, json_data)

    response = client.post(
        f"connections/{connectionId}/subscriptions/hook_trigger_own_env_secret",
        json={
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
            "options": {"option": "opt"},
            "secrets": {"secret": "secretopt"},
        },
    )
    assert response.status_code == 201


@responses.activate
def test_trigger_subscription():
    body = {"messageId": "myid", "message": "This is my message"}
    subscriptionId = mocks.id()
    mocks.get_subscription(mocks.id(), subscriptionId)
    res = mocks.engine_callback()
    trigger = client.post(f"/hook-trigger/{subscriptionId}", json=body)
    assert trigger.status_code == 200
    assert res.call_count == 1


@responses.activate
def test_trigger_subscription_env():
    body = {"messageId": "myid", "message": "This is my message"}
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    mocks.get_subscription(connectionId, subscriptionId)
    res = mocks.engine_callback()
    trigger = client.post(f"/hook-trigger-env-secret/{subscriptionId}", json=body)

    assert trigger.status_code == 200
    assert res.call_count == 1
    assert res.calls[0].request.body is not None
    parsed = json.loads(res.calls[0].request.body)
    assert parsed["payload"]["option"] == "asdf"
    assert parsed["payload"]["secret"] == "asdfasdf"


@responses.activate
def test_trigger_own_subscription_env():
    body = {"messageId": "myid", "message": "This is my message"}
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_subscription(
        connectionId,
        subscriptionId,
        {
            **mocks.default_subscription_data,
            "options": {"option": "test"},
            "secrets": {"secret": "test2"},
        },
    )
    mocks.get_connection(connectionId)
    res = responses.post(
        url="http://v8-engine.com/called",
        status=200,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {mocks.key}"}),
        ],
    )
    trigger = client.post(f"/hook-trigger-own-env/{subscriptionId}", json=body)

    assert trigger.status_code == 200
    assert res.call_count == 1
    assert res.calls[0].request.body is not None
    parsed = json.loads(res.calls[0].request.body)
    assert parsed["payload"]["option"] == "test"
    assert parsed["payload"]["secret"] == "test2"


@responses.activate
def test_trigger_endpoint_fail():
    body = {"messageId": "myid", "message": "This is my message"}
    subscriptionId = mocks.id()
    mocks.get_subscription(mocks.id(), subscriptionId)
    res = mocks.engine_callback(statusCode=404)
    trigger = client.post(f"/hook-trigger/{subscriptionId}", json=body)

    assert trigger.status_code == 404
    assert res.call_count == 1
