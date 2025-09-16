from typing import Annotated, Any, Optional, Type
from fastapi import FastAPI
from pydantic import BaseModel
import requests

Vars = Optional[dict[str, Any]]
OptionsType = Optional[BaseModel]


class StoredConnection(BaseModel):
    id: str
    wfServerId: str
    secrets: Optional[Vars]
    options: Optional[Vars]
    createdAt: str
    updatedAt: str


def connection_endpoint(
    app: FastAPI,
    server_url: str,
    auth_key: str,
    optionsType: Optional[Type[BaseModel]] = None,
    secretsType: Optional[Type[BaseModel]] = None,
):
    class Connection(BaseModel):
        secrets: Annotated[BaseModel, secretsType]
        options: Annotated[BaseModel, optionsType]

    @app.post("/connections", status_code=201)
    def save_connection(connection: Connection):
        return store_connection(
            server_url,
            auth_key,
            connection.options,
            connection.secrets,
        )


def store_connection(
    server_url: str, auth_key: str, options: OptionsType, secrets: OptionsType
):
    headers = {"Authorization": f"Bearer {auth_key}"}

    result = requests.post(
        f"{server_url}/connections",
        headers=headers,
        json={
            "options": options.model_dump() if options else None,
            "secrets": secrets.model_dump() if secrets else None,
        },
    )
    if result.status_code < 300:
        return StoredConnection(**result.json())
    raise Exception(f"Error code: {result.status_code}")
