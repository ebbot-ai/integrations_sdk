from inspect import signature
from fastapi import Body, Depends, FastAPI, HTTPException

from challenger_sdk.component import EbbotComponent
import jsonschema

from challenger_sdk.connection import function_env_from_connection
from challenger_sdk.workflow import WorkflowStorage


def _single_action_endpoints(
    app: FastAPI, storage: WorkflowStorage, fn: EbbotComponent
):
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
        con = storage.get_connection(connection_id)
        sig = signature(fn.call)
        extra_args = {}

        if "env" in sig.parameters:
            extra_args["env"] = function_env_from_connection(fn.env, fn.secrets, con)
        return fn.call(**payload, **extra_args)

    if fn.info:

        @app.get("/connections/{connection_id}/form/" + fn.name)
        def info(connection_id):
            con = storage.get_connection(connection_id)
            if fn.info:
                return fn.info(function_env_from_connection(fn.env, fn.secrets, con))
            return None


def action_endpoints(app: FastAPI, storage: WorkflowStorage, fns: list[EbbotComponent]):
    for fn in fns:
        if len(fn.ebbot_arguments) == 0:
            _single_action_endpoints(app, storage, fn)
