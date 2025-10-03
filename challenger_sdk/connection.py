from typing import Annotated, Any, Optional, Type, Callable
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, model_validator
from challenger_sdk.component import FunctionEnv
from challenger_sdk.workflow import Connection, WorkflowStorage


OptionsType = Optional[BaseModel]


class EmptyOptions(BaseModel):
    pass


ConnectionValidator = Callable[[BaseModel, BaseModel], None]


def connection_endpoints(
    app: FastAPI,
    storage: WorkflowStorage,
    optionsType: Optional[Type[BaseModel]] = EmptyOptions,
    secretsType: Optional[Type[BaseModel]] = EmptyOptions,
    validator: Optional[ConnectionValidator] = None,
):
    class ServerConnection(BaseModel):
        secrets: Annotated[BaseModel, secretsType]
        options: Annotated[BaseModel, optionsType]

        @model_validator(mode="after")
        def valid(self):
            if validator:
                validator(self.secrets, self.options)
            return self

    class ResultConnection(ServerConnection):
        id: str
        wfServerId: str
        createdAt: str
        updatedAt: str

    @app.post("/connections", status_code=201, response_model=ResultConnection)
    def save_connection(connection: ServerConnection):
        return storage.save_connection(
            connection.options.model_dump(),
            connection.secrets.model_dump(),
        )

    @app.get("/connections/{connectionId}", response_model=ResultConnection)
    def get_connection_endpoint(connectionId: str):
        return storage.get_connection(connectionId)


def function_env_from_connection(env: list[str], secrets: list[str], con: Connection):
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
