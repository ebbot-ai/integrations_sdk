from typing import TypeVar, override
from dataclasses import dataclass
from typing import Type, override

from fastapi import HTTPException
from pydantic import BaseModel
import requests
from challenger_sdk.workflow import (
    Connection,
    NewSubscription,
    Subscription,
    Vars,
    WorkflowStorage,
)


@dataclass
class StorageServerWorkflowStorage(WorkflowStorage):
    server_url: str
    auth_key: str

    @override
    def save_connection(self, options: Vars = None, secrets: Vars = None) -> Connection:
        breakpoint()
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


def request_headers(auth_key: str) -> dict:
    return {"Authorization": f"Bearer {auth_key}"}


T = TypeVar("T", bound=BaseModel)


def _response_handler(result: requests.Response, Model: Type[T]) -> T:
    if result.status_code < 300:
        return Model(**result.json())
    if result.status_code == 404:
        raise HTTPException(status_code=result.status_code, detail="not found")
    raise Exception(f"Error code: {result.status_code}")
