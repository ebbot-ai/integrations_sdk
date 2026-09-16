import logging
from inspect import signature
from typing import Any, Callable, cast

from fastapi import Body, Depends, FastAPI, HTTPException

from integrations_sdk.component import EbbotComponent, InfoReturnType
import jsonschema

from integrations_sdk.connection import function_env_from_connection
from integrations_sdk.workflow import WorkflowStorage


logger = logging.getLogger(__name__)


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
        logger.debug(
            "Action called: %s for connection %s",
            fn.name,
            connection_id,
            extra={"payload_keys": sorted(payload.keys())},
        )
        con = storage.get_connection(connection_id)
        sig = signature(fn.call)
        extra_args = {}

        if "env" in sig.parameters:
            extra_args["env"] = function_env_from_connection(fn.env, fn.secrets, con)
        return fn.call(**payload, **extra_args)

    if fn.info:

        def form_info(connection_id: str, selected: dict[str, Any]):
            con = storage.get_connection(connection_id)
            if fn.info:
                env = function_env_from_connection(fn.env, fn.secrets, con)
                info_callback = cast(Callable[..., InfoReturnType], fn.info)
                if len(signature(info_callback).parameters) > 1:
                    return info_callback(env, selected)
                return info_callback(env)
            return None

        @app.get("/connections/{connection_id}/form/" + fn.name)
        def info(connection_id: str):
            return form_info(connection_id, {})

        @app.post("/connections/{connection_id}/form/" + fn.name)
        def info_with_selected_values(
            connection_id: str, selected: dict[str, Any] = Body(embed=True)
        ):
            return form_info(connection_id, selected)


def action_endpoints(app: FastAPI, storage: WorkflowStorage, fns: list[EbbotComponent]):
    for fn in fns:
        if len(fn.ebbot_arguments) == 0:
            _single_action_endpoints(app, storage, fn)
