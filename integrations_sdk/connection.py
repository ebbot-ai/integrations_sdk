from typing import Annotated, Any, Callable, Optional, Type
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError, model_validator
from integrations_sdk.component import FunctionEnv
from integrations_sdk.errors import SafeValidationError
from integrations_sdk.workflow import Connection, WorkflowStorage


OptionsType = Optional[BaseModel]


class EmptyOptions(BaseModel):
    pass


ConnectionValidator = Callable[[BaseModel, BaseModel], None]
GetPostInstallEnvFn = Callable[[], FunctionEnv]
PostInstallInstructionsCallback = Callable[[Connection, GetPostInstallEnvFn], str]


def connection_endpoints(
    app: FastAPI,
    storage: WorkflowStorage,
    optionsType: Optional[Type[BaseModel]] = EmptyOptions,
    secretsType: Optional[Type[BaseModel]] = EmptyOptions,
    validator: Optional[ConnectionValidator] = None,
    post_install_instructions: Optional[PostInstallInstructionsCallback] = None,
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
        postInstallInstructions: Optional[str] = None

    class GetResultConnection(BaseModel):
        id: str
        wfServerId: str
        options: Annotated[BaseModel, optionsType]
        createdAt: str
        updatedAt: str
        postInstallInstructions: Optional[str] = None

    def build_result(connection: Connection) -> ResultConnection:
        data = connection.model_dump()
        if post_install_instructions:
            data["postInstallInstructions"] = post_install_instructions(
                connection, lambda: _get_connection_env(connection)
            )
        return ResultConnection(**data)

    def build_get_result(connection: Connection) -> GetResultConnection:
        data = connection.model_dump(exclude={"secrets"})
        if post_install_instructions:
            data["postInstallInstructions"] = post_install_instructions(
                connection, lambda: _get_connection_env(connection)
            )
        return GetResultConnection(**data)

    @app.post("/connections", status_code=201, response_model=ResultConnection)
    def save_connection(connection: ServerConnection):
        saved_connection = storage.save_connection(
            connection.options.model_dump(),
            connection.secrets.model_dump(),
        )
        return build_result(saved_connection)

    @app.get("/connections/{connectionId}", response_model=GetResultConnection)
    def get_connection_endpoint(connectionId: str):
        try:
            connection = storage.get_connection(connectionId)
            return build_get_result(connection)
        except ValidationError as e:
            raise SafeValidationError(e) from None


def function_env_from_connection(env: list[str], secrets: list[str], con: Connection):
    return FunctionEnv(
        _pick_env_vars(env, con.options if con.options else {}),
        _pick_env_vars(secrets, con.secrets if con.secrets else {}),
    )


def _get_connection_env(con: Connection) -> FunctionEnv:
    return FunctionEnv(con.options or {}, con.secrets or {})


def _pick_env_vars(vars: list[str], env: dict[str, Any]) -> dict[str, str]:
    picked: dict[str, str] = {}
    for var in vars:
        if var not in env:
            raise HTTPException(status_code=500, detail=f"Missing env var: {var}")
        picked[var] = env[var]
    return picked
