from typing import Annotated, Any, Optional, Type
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

from challenger_sdk.component import FunctionEnv
from challenger_sdk.storage_api import request_headers

Vars = Optional[dict[str, Any]]
OptionsType = Optional[BaseModel]


class StoredConnection(BaseModel):
    id: str
    wfServerId: str
    secrets: Vars
    options: Vars
    createdAt: str
    updatedAt: str


class EmptyOptions(BaseModel):
    pass


def connection_endpoints(
    app: FastAPI,
    server_url: str,
    auth_key: str,
    optionsType: Optional[Type[BaseModel]] = EmptyOptions,
    secretsType: Optional[Type[BaseModel]] = EmptyOptions,
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
    @app.get("/connections/{connectionId}")
    def get_connection_endpoint(connectionId: str) -> StoredConnection:
        return get_connection(
            server_url,
            auth_key,
            connectionId
        )



def store_connection(
    server_url: str, auth_key: str, options: OptionsType, secrets: OptionsType
):
    return _response_handler(
        requests.post(
            f"{server_url}/connections",
            headers=request_headers(auth_key),
            json={
                "options": options.model_dump() if options else None,
                "secrets": secrets.model_dump() if secrets else None,
            },
        )
    )


def function_env_from_connection(
    env: list[str], secrets: list[str], con: StoredConnection
):
    return FunctionEnv(
        _pick_env_vars(env, con.options if con.options else {}),
        _pick_env_vars(secrets, con.secrets if con.secrets else {}),
    )


def _pick_env_vars(vars: list[str], env: dict[str, Any]) -> dict[str, str]:
    picked: dict[str, str] = {}
    for var in vars:
        if var not in env:
            raise HTTPException(status_code=500, detail=f"Missing env var: {var}")
        picked[var] = env[var]
    return picked


def get_connection(server_url: str, auth_key: str, con_id: str):
    return _response_handler(
        requests.get(
            f"{server_url}/connections/{con_id}",
            headers=request_headers(auth_key),
        )
    )


def _response_handler(result: requests.Response):
    if result.status_code < 300:
        return StoredConnection(**result.json())
    if result.status_code == 404:
        raise HTTPException(status_code=result.status_code, detail="not found")
    raise Exception(f"Error code: {result.status_code}")
