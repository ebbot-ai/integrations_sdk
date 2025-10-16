from uuid import uuid4
from datetime import datetime, timezone
import responses

default_json_body = {
    "options": {"notSecret": "asdf"},
    "secrets": {"secret": "asdfasdf"},
}
key = "hpM9ZHBvrxlly61irrdoGmnYmdPX5K883eyXtp1jc7vmiowV29tqAJuodLr1uBgD"


def id():
    return str(uuid4())


wf_server_id = id()


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def post_connection(id: str, json_body=default_json_body):
    iso_now = now()
    return responses.post(
        url="http://localhost:9000/connections",
        status=201,
        match=[
            responses.matchers.json_params_matcher(json_body),
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={
            **json_body,
            "id": id,
            "wfServerId": wf_server_id,
            "createdAt": iso_now,
            "updatedAt": iso_now,
        },
    )


def get_connection(id: str, json_body=default_json_body):
    iso_now = now()
    return responses.get(
        url=f"http://localhost:9000/connections/{id}",
        status=201,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={
            **json_body,
            "id": id,
            "wfServerId": wf_server_id,
            "createdAt": iso_now,
            "updatedAt": iso_now,
        },
    )


default_subscription_data = {
    "name": "hook_trigger",
    "callback": {
        "type": "http",
        "method": "post",
        "url": "http://v8-engine.com/called",
    },
    "options": {},
    "secrets": {},
}


def post_subscription(
    connectionId: str, subscriptionId: str, data: dict = default_subscription_data
):
    return responses.post(
        url=f"http://localhost:9000/connections/{connectionId}/subscriptions",
        status=201,
        match=[
            responses.matchers.json_params_matcher(data),
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
        json={**data, "id": subscriptionId, "connectionId": connectionId},
    )


def patch_subscription(
    connectionId: str, subscriptionId: str, data=default_subscription_data
):
    return responses.patch(
        url=f"http://localhost:9000/connections/{connectionId}/subscriptions/{subscriptionId}",
        status=201,
        json={**data, "id": subscriptionId, "connectionId": connectionId},
    )


def delete_subscription(connectionId: str, subscriptionId: str):
    return responses.delete(
        url=f"http://localhost:9000/connections/{connectionId}/subscriptions/{subscriptionId}",
        status=204,
    )


def get_subscription(
    connectionId: str, subscriptionId: str, data=default_subscription_data
):
    return responses.get(
        url=f"http://localhost:9000/subscriptions/{subscriptionId}",
        json={
            **data,
            "id": subscriptionId,
            "connectionId": connectionId,
        },
        status=200,
    )


def engine_callback(url="http://v8-engine.com/called", statusCode=200):
    return responses.post(
        url=url,
        status=statusCode,
        match=[
            responses.matchers.header_matcher({"Authorization": f"Bearer {key}"}),
        ],
    )


def get_subscriptions(
    subscriptions: list[dict] | None = None,
    total: int | None = None,
    name: str | None = None,
):
    if subscriptions is None:
        # provide a default subscription entry
        subscriptionId = id()
        connectionId = id()
        subscriptions = [
            {
                **default_subscription_data,
                "id": subscriptionId,
                "connectionId": connectionId,
            }
        ]
    if total is None:
        total = len(subscriptions)

    matchers = [responses.matchers.header_matcher({"Authorization": f"Bearer {key}"})]
    if name is not None:
        # ensure the request includes the correct 'name' query param when provided
        matchers.append(
            responses.matchers.query_param_matcher(
                {"name": name, "limit": "1000", "offset": "0"}
            )
        )

    return responses.get(
        url="http://localhost:9000/subscriptions",
        status=200,
        match=matchers,
        json={"total": total, "data": subscriptions},
    )
