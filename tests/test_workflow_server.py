from fastapi.testclient import TestClient
from pydantic import BaseModel
import logging
import responses
from pytest import raises
import json
import mocks
from integrations_sdk.server import start_workflow_server


class Options(BaseModel):
    notSecret: str


class Secrets(BaseModel):
    secret: str


def validator(secrets, options):
    if options.notSecret == secrets.secret:
        raise ValueError("Secret can't be the same as not secret")


def connection_post_install_instructions(connection, get_env):
    env = get_env()
    return f"post install instructions for {connection.id} {env.secrets['secret']}"


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
def test_workflow_server_connection_post_install_instructions():
    id = mocks.id()
    post_install_app = start_workflow_server(
        "fns",
        "http://localhost:9000",
        mocks.key,
        Options,
        Secrets,
        validator=validator,
        post_install_instructions=connection_post_install_instructions,
    )
    post_install_client = TestClient(post_install_app)
    mocks.post_connection(id)
    mocks.get_connection(id)
    response = post_install_client.post("/connections", json=json_body)
    assert response.status_code == 201
    data = response.json()
    assert (
        data["postInstallInstructions"]
        == f"post install instructions for {data['id']} {json_body['secrets']['secret']}"
    )
    get_response = post_install_client.get(f"/connections/{data['id']}")
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert (
        get_data["postInstallInstructions"]
        == f"post install instructions for {get_data['id']} {json_body['secrets']['secret']}"
    )


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
def test_get_connection_validation_error_omits_input_data():
    connection_id = mocks.id()
    responses.get(
        url=f"http://localhost:9000/connections/{connection_id}",
        status=201,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {mocks.key}"}),
        ],
        json={
            "id": connection_id,
            "wfServerId": mocks.wf_server_id,
            "createdAt": mocks.now(),
            "updatedAt": mocks.now(),
            "options": {"notSecrett": "asdf"},
            "secrets": {"secret": "asdfasdf"},
        },
    )

    with raises(Exception, match="Field required") as exc:
        client.get(f"/connections/{connection_id}")

    message = str(exc.value)
    assert "Field required" in message
    assert "'input'" not in message
    assert "notSecrett" not in message
    assert "asdfasdf" not in message


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
def test_action_endpoint_logs_action_called(caplog):
    id = mocks.id()
    mocks.get_connection(id)

    with caplog.at_level(logging.DEBUG):
        result = client.post(
            f"connections/{id}/call/say_hello_with_secret_and_env",
            json={"password": "currywurst"},
        )

    assert result.status_code == 200
    assert any(
        record.name == "integrations_sdk.actions"
        and "Action called: say_hello_with_secret_and_env" in record.getMessage()
        for record in caplog.records
    )


def test_action_manifest():
    manifest = client.get("/manifest")
    data = manifest.json()
    # Assert that action 'say_hello' exists and has displayName 'Say hello'
    say_hello = next((a for a in data["actions"] if a["name"] == "say_hello"), None)
    assert say_hello is not None
    assert say_hello.get("displayName") == "Say hello"
    # Assert that action 'say_hello_pydantic has a valid schema
    say_hello_pydantic = next(
        (a for a in data["actions"] if a["name"] == "say_hello_pydantic"), None
    )
    assert say_hello_pydantic is not None
    assert (
        say_hello_pydantic["schema"]["call"]["function"]["parameters"]["properties"][
            "name"
        ]["type"]
        == "string"
    )


def test_manifest_metadata():
    metadata_app = start_workflow_server(
        "fns",
        "http://localhost:9000",
        mocks.key,
        Options,
        Secrets,
        api_rate_limit_info="100 requests per minute",
        required_permissions="contacts:read",
        email="support@example.com",
        author="Example Author",
        url="https://example.com",
    )
    metadata_client = TestClient(metadata_app)
    manifest = metadata_client.get("/manifest")
    data = manifest.json()
    assert data.get("apiRateLimitInfo") == "100 requests per minute"
    assert data.get("requiredPermissions") == "contacts:read"
    assert data.get("email") == "support@example.com"
    assert data.get("author") == "Example Author"
    assert data.get("url") == "https://example.com"


@responses.activate
def test_action_pydantic_arguments():
    id = mocks.id()
    mocks.get_connection(id)

    result = client.post(
        f"connections/{id}/call/say_hello_pydantic",
        json={"name": "Test"},
    )
    data = result.json()
    assert result.status_code == 200
    data = result.json()
    assert data["result"] == "Hello Test"


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
    assert data["word"]["description"] == "A more detailed description"
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
            "data": {
                "options": {},
                "secrets": {},
            },
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
            "data": {
                "options": {},
                "secrets": {},
            },
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
                "data": {
                    "options": {},
                    "secrets": {},
                },
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
            "data": {
                "options": {"option": "opt"},
                "secrets": {"secret": "secretopt"},
            },
        },
    )
    assert response.status_code == 201


@responses.activate
def test_delete_subscription():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    remove_req = mocks.delete_subscription(connectionId, subscriptionId)
    response = client.delete(
        f"connections/{connectionId}/subscriptions/{subscriptionId}",
    )
    assert response.status_code == 204
    assert remove_req.call_count == 1


@responses.activate
def test_delete_subscription_missing():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    remove_req = responses.delete(
        url=f"http://localhost:9000/connections/{connectionId}/subscriptions/{subscriptionId}",
        status=404,
    )
    response = client.delete(
        f"connections/{connectionId}/subscriptions/{subscriptionId}",
    )
    assert response.status_code == 404
    assert remove_req.call_count == 1


@responses.activate
def test_subscription_get_connection_subscriptions():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    mocks.get_connection_subscriptions(
        connectionId,
        [
            {
                **mocks.default_subscription_data,
                "name": "post_install_instructions_trigger",
                "id": subscriptionId,
                "connectionId": connectionId,
                "options": {"some": "option"},
                "secrets": {"some": "secret"},
            }
        ],
    )
    response = client.get(f"connections/{connectionId}/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["data"]["options"]["some"] == "option"
    assert "secrets" not in data["data"][0]["data"]
    assert (
        data["data"][0]["postInstallInstructions"]
        == f"install instructions for subscription subscription {subscriptionId}"
    )


@responses.activate
def test_subscription_get():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_subscription(
        connectionId,
        subscriptionId,
        {
            **mocks.default_subscription_data,
            "name": "post_install_instructions_trigger",
            "id": subscriptionId,
            "connectionId": connectionId,
            "options": {"some": "option"},
            "secrets": {"some": "secret"},
        },
    )
    response = client.get(f"connections/{connectionId}/subscriptions/{subscriptionId}")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["options"]["some"] == "option"
    assert "secrets" not in data["data"]
    assert (
        data["postInstallInstructions"]
        == f"install instructions for subscription subscription {subscriptionId}"
    )


@responses.activate
def test_subscription_get_other_404():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_subscription(connectionId, subscriptionId)
    response = client.get(f"connections/{mocks.id()}/subscriptions/{subscriptionId}")
    assert response.status_code == 404


@responses.activate
def test_trigger_get_env_validation_error_omits_input_data():
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    mocks.get_subscription(
        connectionId,
        subscriptionId,
        {
            **mocks.default_subscription_data,
            "name": "hook_trigger_own_env_secret",
            "options": {"wrong_option": "test"},
            "secrets": {"secret": "super-secret"},
        },
    )

    with raises(Exception, match="Field required") as exc:
        client.post(f"/hook-trigger-own-env/{subscriptionId}")

    message = str(exc.value)
    assert "Field required" in message
    assert "'input'" not in message
    assert "wrong_option" not in message
    assert "super-secret" not in message


@responses.activate
def test_trigger_subscription():
    body = {"messageId": "myid", "message": "This is my message"}
    subscriptionId = mocks.id()
    mocks.get_subscription(mocks.id(), subscriptionId)
    res = mocks.engine_callback()
    trigger = client.post(f"/hook-trigger/{subscriptionId}", json=body)
    assert trigger.status_code == 200
    assert res.call_count == 1
    assert res.calls[0].request.body is not None
    parsed = json.loads(res.calls[0].request.body)
    assert parsed["metadata"]["referenceId"] == "myid"
    assert parsed["metadata"]["data"]["message"] == "This is my message"


@responses.activate
def test_trigger_subscription_logs_trigger_called(caplog):
    body = {"messageId": "myid", "message": "This is my message"}
    subscriptionId = mocks.id()
    mocks.get_subscription(mocks.id(), subscriptionId)
    mocks.engine_callback()

    with caplog.at_level(logging.DEBUG):
        trigger = client.post(f"/hook-trigger/{subscriptionId}", json=body)

    assert trigger.status_code == 200
    assert any(
        record.name == "integrations_sdk.triggers"
        and "Trigger triggered: hook_trigger" in record.getMessage()
        for record in caplog.records
    )


@responses.activate
def test_auth_token_required():
    secure_app = start_workflow_server(
        "fns",
        "http://localhost:9000",
        mocks.key,
        Options,
        Secrets,
        validator=validator,
        auth_token="supersecret",
    )
    secure_client = TestClient(secure_app)

    # Missing header
    r = secure_client.get("/manifest")
    assert r.status_code == 401

    # Wrong header
    r = secure_client.get("/manifest", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401

    # Correct header
    r = secure_client.get("/manifest", headers={"Authorization": "Bearer supersecret"})
    assert r.status_code == 200

    # Triggers should be accessible without a token.
    body = {"messageId": "myid", "message": "This is my message"}
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    mocks.get_subscription(connectionId, subscriptionId)
    mocks.engine_callback()
    trigger = client.post(f"/hook-trigger-env-secret/{subscriptionId}", json=body)
    assert trigger.status_code == 200


def test_auth_token_logs_failed_requests(caplog):
    secure_app = start_workflow_server(
        "fns",
        "http://localhost:9000",
        mocks.key,
        Options,
        Secrets,
        validator=validator,
        auth_token="supersecret",
    )
    secure_client = TestClient(secure_app)

    with caplog.at_level(logging.WARNING):
        response = secure_client.get("/manifest")

    assert response.status_code == 401
    assert any(
        record.name == "integrations_sdk.server"
        and "Authentication failed for GET /manifest" in record.getMessage()
        and "authorization header missing" in record.getMessage()
        for record in caplog.records
    )


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


@responses.activate
def test_trigger_multiple_first():
    body = {
        "type": "hook_trigger",
        "messageId": "myid",
        "message": "This is my message",
    }
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    sub_data = {
        **mocks.default_subscription_data,
        "connectionId": connectionId,
        "id": subscriptionId,
    }
    mocks.get_subscription(connectionId, subscriptionId)
    mocks.get_subscriptions(subscriptions=[sub_data], total=1, name="hook_trigger")
    res = mocks.engine_callback()
    trigger = client.post("/multiple-triggers", json=body)
    assert trigger.status_code == 200
    assert res.call_count == 1
    assert res.calls[0].request.body is not None
    parsed = json.loads(res.calls[0].request.body)
    assert parsed["payload"]["messageId"] == "myid"
    assert parsed["payload"]["message"] == "This is my message"


@responses.activate
def test_trigger_multiple_second():
    body = {
        "type": "hook_trigger_secret",
        "messageId": "myid",
        "message": "This is my message",
    }
    connectionId = mocks.id()
    subscriptionId = mocks.id()
    mocks.get_connection(connectionId)
    sub_data = {
        **mocks.default_subscription_data,
        "connectionId": connectionId,
        "id": subscriptionId,
        "name": "hook_trigger_own_env_secret",
        "options": {"option": "test"},
        "secrets": {"secret": "test2"},
    }
    mocks.get_subscription(connectionId, subscriptionId, sub_data)
    mocks.get_subscriptions(
        subscriptions=[sub_data], total=1, name="hook_trigger_own_env_secret"
    )
    res = mocks.engine_callback()
    trigger = client.post("/multiple-triggers", json=body)
    assert trigger.status_code == 200
    assert res.call_count == 1
    assert res.calls[0].request.body is not None
    parsed = json.loads(res.calls[0].request.body)
    assert parsed["payload"]["option"] == "test"
    assert parsed["payload"]["secret"] == "test2"


@responses.activate
def test_get_subscriptions_trigger():
    con_id = mocks.id()
    mocks.get_connection(con_id)
    # create 5 subscriptions for multisub_trigger with unique names
    unique_names = [f"unique-{i}" for i in range(5)]
    subscriptions: list[dict] = []
    id_pairs: list[tuple[str, str]] = []

    for i, name in enumerate(unique_names):
        sub_id = mocks.id()

        subscription_data = {
            "id": sub_id,
            "connectionId": con_id,
            "name": "multisub_trigger",
            "callback": {
                "type": "http",
                "method": "post",
                "url": "http://v8-engine.com/called",
            },
            "options": {"name": name},
            "secrets": {},
        }
        subscriptions.append({**subscription_data})
        id_pairs.append((sub_id, name))
        mocks.get_subscription(con_id, sub_id, subscription_data)
    mocks.get_subscriptions(subscriptions=subscriptions, total=len(subscriptions))
    res = mocks.engine_callback()
    response = client.get("/endpoint")
    assert response.status_code == 200
    assert res.call_count == len(subscriptions)
    name_map = {sub_id: name for sub_id, name in id_pairs}
    for call in res.calls:
        assert call.request.body is not None
        data = json.loads(call.request.body)
        payload = data["payload"]
        assert payload["messageId"] in name_map
        assert payload["message"] == name_map[payload["messageId"]]
