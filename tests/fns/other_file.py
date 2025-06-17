from challenger_sdk.component import ToolResult, component


@component(
    description="This function adds the visitor's email and name to the conversation. Always explicitly request this information from the user if it is not already provided in the input—never invent or assume details. This function is used by other functions that depend on accurate visitor identification.",
    ebbot_arguments=[],
    llm_arguments={
        "email": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their email address. Let the user verify it is correct before proceeding.",
        },
        "first_name": {
            "required": True,
            "type": "string",
            "description": "Ask the user about their name. Let the user verify it is correct before proceeding.",
        },
        "last_name": {
            "required": False,
            "type": "string",
            "description": "Ask the user about their last name.",
        },
    },
)
def update_user(
    email: str, first_name: str, last_name: str | None = None
) -> ToolResult:
    return {
        "result": "User info recorded!",
        "actions": [
            {
                "type": "patch_user",
                "data": {
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name if last_name else "",
                },
            }
        ],
    }
