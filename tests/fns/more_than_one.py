from integrations_sdk.component import ToolResult, component
from integrations_sdk.ebbot import User
from dataclasses import asdict


@component(
    description="Fetch information from our database about what we stored about them. If you get empyt info, tell the user we have no information.",
    ebbot_arguments=["user"],
)
def retrieve_user(user: User) -> ToolResult:
    return {"result": asdict(user)}


@component(
    description="The user wants to tell you about their favorite food.",
    ebbot_arguments=[],
    llm_arguments={
        "dish": {
            "required": True,
            "type": "string",
            "description": "The users favorite food.",
        },
    },
)
def store_favorite_food(dish: str) -> ToolResult:
    return {
        "result": "Food recorded!",
        "actions": [
            {
                "type": "store",
                "data": {"dish": dish},
            }
        ],
    }
