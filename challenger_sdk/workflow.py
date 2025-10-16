from typing import Any, Literal, Optional, Protocol
from pydantic import BaseModel


Vars = Optional[dict[str, Any]]


class Connection(BaseModel):
    id: str
    wfServerId: str
    secrets: Vars
    options: Vars
    createdAt: str
    updatedAt: str


class Callback(BaseModel):
    type: Literal["http"]
    method: Literal["post"]
    url: str


class NewSubscription(BaseModel):
    callback: Callback
    name: str
    options: Optional[dict[str, Any]] = None
    secrets: Optional[dict[str, Any]] = None


class Subscription(NewSubscription):
    id: str
    connectionId: str

class SubscriptionResult(BaseModel):
    total: int
    data: list[Subscription]

class WorkflowStorage(Protocol):
    def save_connection(
        self, options: Vars = None, secrets: Vars = None
    ) -> Connection: ...

    def get_connection(self, connectionId: str) -> Connection: ...

    def save_subscription(
        self, connectionId: str, subscription: NewSubscription
    ) -> Subscription: ...

    def get_subscription(self, subscriptionId: str) -> Subscription: ...

    def remove_subscription(self, connectionId: str, subscriptionId: str): ...

    def update_subscription(self, subscription: Subscription) -> Subscription: ...

    def get_subscriptions(
        self, limit: int = 1000, offset: int = 0, name: Optional[str] = None
    ) -> SubscriptionResult: ...
