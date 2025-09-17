from typing import Annotated, Any, Optional, Type
from fastapi import FastAPI, HTTPException
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
    return _response_handler(
        requests.post(
            f"{server_url}/connections",
            headers=_request_headers(auth_key),
            json={
                "options": options.model_dump() if options else None,
                "secrets": secrets.model_dump() if secrets else None,
            },
        )
    )


def get_connection(server_url: str, auth_key: str, con_id: str):
    return _response_handler(
        requests.get(
            f"{server_url}/connections/{con_id}",
            headers=_request_headers(auth_key),
        )
    )


def _response_handler(result: requests.Response):
    if result.status_code < 300:
        return StoredConnection(**result.json())
    if result.status_code == 404:
        raise HTTPException(status_code=result.status_code, detail="not found")
    raise Exception(f"Error code: {result.status_code}")


def _request_headers(auth_key: str) -> dict:
    return {"Authorization": f"Bearer {auth_key}"}
