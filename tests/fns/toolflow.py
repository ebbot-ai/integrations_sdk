from pydantic import BaseModel
from challenger_sdk.component import ToolResult, workflow_action


class Result(BaseModel):
    result: str


@workflow_action(
    description="Say hello.",
    result=Result,
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
)
def say_hello(name: str) -> Result:
    return Result(result=f"Hello {name}")


@workflow_action(
    description="Say hello, the good old fashined way",
    result=Result.model_json_schema(),
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
)
def say_hello_without_pydantic(name: str) -> dict:
    return Result(result=f"Hello {name}").model_dump()
