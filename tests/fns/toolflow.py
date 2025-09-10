from challenger_sdk.component import ToolResult, workflow_action


@workflow_action(
    description="Say hello.",
    arguments={
        "name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        }
    },
)
def say_hello(name: str) -> ToolResult:
    return {
        "result": f"Hello {name}",
    }
