from inspect import signature
from typing import Any
from fastapi import Body, Depends, FastAPI, HTTPException

from challenger_sdk.component import EbbotComponent, FunctionEnv
import jsonschema

from challenger_sdk.connection import function_env_from_connection, get_connection


def action_endpoint(app: FastAPI, server_url: str, auth_key: str, fn: EbbotComponent):
    schema = fn.llm_schema()
    json_schema = schema["function"]["parameters"]

    def validate_against_schema(payload: dict = Body()):
        try:
            jsonschema.validate(payload, json_schema)
        except jsonschema.ValidationError as e:
            raise HTTPException(status_code=422, detail=e.message)
        return payload

    @app.post(
        "/connections/{connection_id}/call/" + fn.name,
        openapi_extra={
            "requestBody": {"content": {"application/json": {"schema": json_schema}}}
        },
    )
    def action(connection_id: str, payload: dict = Depends(validate_against_schema)):
        con = get_connection(server_url, auth_key, connection_id)
        sig = signature(fn.call)
        extra_args = {}

        if "env" in sig.parameters:
            extra_args["env"] = function_env_from_connection(fn.env, fn.secrets, con)
        return fn.call(**payload, **extra_args)


def action_endpoints(
    app: FastAPI, server_url: str, auth_key: str, fns: list[EbbotComponent]
):
    for fn in fns:
        if len(fn.ebbot_arguments) == 0:
            action_endpoint(app, server_url, auth_key, fn)
