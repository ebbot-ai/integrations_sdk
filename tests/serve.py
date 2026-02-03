from integrations_sdk.server import start_workflow_server

installInstructions = "asdf"
docs = "docs"

app = start_workflow_server(
    "fns",
    "http://server.com",
    "key",
    install_instructions=installInstructions,
    docs=docs,
)
