from typing import TypeVar, override
from dataclasses import dataclass
from typing import Type
from fastapi import HTTPException
from pydantic import BaseModel
import requests
from integrations_sdk.workflow import (
    Connection,
    NewSubscription,
    Subscription,
    Vars,
    WorkflowStorage,
    SubscriptionResult,
)


@dataclass
class StorageServerWorkflowStorage(WorkflowStorage):
    server_url: str
    auth_key: str

    @override
    def save_connection(self, options: Vars = None, secrets: Vars = None) -> Connection:
        return _response_handler(
            requests.post(
                f"{self.server_url}/connections",
                headers=request_headers(self.auth_key),
                json={
                    "options": options if options else {},
                    "secrets": secrets if secrets else {},
                },
            ),
            Connection,
        )

    @override
    def get_connection(self, connectionId: str) -> Connection:
        return _response_handler(
            requests.get(
                f"{self.server_url}/connections/{connectionId}",
                headers=request_headers(self.auth_key),
            ),
            Connection,
        )

    @override
    def save_subscription(
        self, connectionId: str, subscription: NewSubscription
    ) -> Subscription:
        return _response_handler(
            requests.post(
                f"{self.server_url}/connections/{connectionId}/subscriptions",
                headers=request_headers(self.auth_key),
                json=subscription.model_dump(),
            ),
            Subscription,
        )

    @override
    def get_subscription(self, subscriptionId: str) -> Subscription:
        return _response_handler(
            requests.get(
                f"{self.server_url}/subscriptions/{subscriptionId}",
                headers=request_headers(self.auth_key),
            ),
            Subscription,
        )

    @override
    def remove_subscription(self, connectionId: str, subscriptionId: str):
        result = requests.delete(
            f"{self.server_url}/connections/{connectionId}/subscriptions/{subscriptionId}",
            headers=request_headers(self.auth_key),
        )
        if result.status_code == 404:
            raise HTTPException(status_code=result.status_code, detail="not found")
        if result.status_code > 300:
            raise Exception(f"Error code: {result.status_code}")

    @override
    def update_subscription(self, subscription: Subscription) -> Subscription:
        payload: dict = {}
        if subscription.options is not None:
            payload["options"] = subscription.options
        if subscription.secrets is not None:
            payload["secrets"] = subscription.secrets

        return _response_handler(
            requests.patch(
                f"{self.server_url}/connections/{subscription.connectionId}/subscriptions/{subscription.id}",
                headers=request_headers(self.auth_key),
                json=payload,
            ),
            Subscription,
        )

    @override
    def get_subscriptions(
        self, limit: int = 1000, offset: int = 0, name: str | None = None
    ):
        params: dict[str, int | str] = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        result = requests.get(
            f"{self.server_url}/subscriptions",
            headers=request_headers(self.auth_key),
            params=params,
        )
        return _response_handler(result, SubscriptionResult)

    @override
    def get_connection_subscriptions(
        self,
        connectionId: str,
        limit: int = 1000,
        offset: int = 0,
        name: str | None = None,
    ) -> SubscriptionResult:
        params: dict[str, int | str] = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        result = requests.get(
            f"{self.server_url}/connections/{connectionId}/subscriptions",
            headers=request_headers(self.auth_key),
            params=params,
        )
        return _response_handler(result, SubscriptionResult)


def request_headers(auth_key: str) -> dict:
    return {"Authorization": f"Bearer {auth_key}"}


T = TypeVar("T", bound=BaseModel)


def _response_handler(result: requests.Response, Model: Type[T]) -> T:
    if result.status_code < 300:
        return Model(**result.json())
    if result.status_code == 404:
        raise HTTPException(status_code=result.status_code, detail="not found")
    raise Exception(f"Error code: {result.status_code}")
