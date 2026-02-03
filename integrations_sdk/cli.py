import dataclasses
from typing import Optional, List
import typer
import requests
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))


app = typer.Typer()


@dataclasses.dataclass
class Env:
    url: str
    token: str
    bot_id: str


def get_env(bot_id: str | None) -> Env:
    url = os.getenv("CHALLENGER_URL")
    if not url:
        raise Exception(
            "Challenger URL not present in your env file or your environment."
        )
    token = os.getenv("CHALLENGER_TOKEN")
    if not token:
        raise Exception(
            "CHALLENGER_TOKEN not present in your env file or your environment."
        )

    if not bot_id:
        bot_id = os.getenv("BOT_ID")

    if not bot_id:
        raise Exception(
            "Bot ID must be provided either as an argument or as a BOT_ID environment variable."
        )
    return Env(url, token, bot_id)


def get_headers(env: Env) -> dict[str, str]:
    return {"Authorization": f"Bearer {env.token}"}


@app.command()
def create_secret(name: str, secret: str, bot_id: str | None = None):
    env = get_env(bot_id)
    data = {"name": name, "secret": secret}

    response = requests.post(
        f"{env.url}/api/bots/{env.bot_id}/secrets", json=data, headers=get_headers(env)
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not save secret: {response.status_code} {response.reason}"
        )
    print("Secret saved successfully!")


@app.command()
def create_env(name: str, value: str, bot_id: str | None = None):
    env = get_env(bot_id)
    data = {"name": name, "value": value}
    response = requests.post(
        f"{env.url}/api/bots/{env.bot_id}/env-variables",
        json=data,
        headers=get_headers(env),
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not save env variable: {response.status_code} {response.reason}"
        )
    print("Environment variable saved successfully!")


@dataclasses.dataclass
class Config:
    debug: Optional[bool] = None
    persona: Optional[str] = None
    mcpServers: Optional[list[str]] = None
    endeavourServers: Optional[list[str]] = None


@app.command()
def set_debug(debug: bool, bot_id: str | None = None):
    env = get_env(bot_id)
    config = Config(debug=debug)
    data = dataclasses.asdict(
        config, dict_factory=lambda d: {k: v for k, v in d if v is not None}
    )
    response = requests.patch(
        f"{env.url}/api/bots/{env.bot_id}/config",
        json=data,
        headers=get_headers(env),
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not set debug flag: {response.status_code} {response.reason}"
        )
    print("Debug flag set successfully!")


@app.command()
def set_persona(persona: str, bot_id: str | None = None):
    env = get_env(bot_id)
    config = Config(persona=persona)
    data = dataclasses.asdict(
        config, dict_factory=lambda d: {k: v for k, v in d if v is not None}
    )
    response = requests.patch(
        f"{env.url}/api/bots/{env.bot_id}/config",
        json=data,
        headers=get_headers(env),
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not set persona: {response.status_code} {response.reason}"
        )
    print("Persona set successfully!")


@app.command()
def set_mcp_servers(servers: List[str], bot_id: str | None = None):
    env = get_env(bot_id)
    config = Config(mcpServers=servers)
    data = dataclasses.asdict(
        config, dict_factory=lambda d: {k: v for k, v in d if v is not None}
    )
    response = requests.patch(
        f"{env.url}/api/bots/{env.bot_id}/config",
        json=data,
        headers=get_headers(env),
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not set MCP servers: {response.status_code} {response.reason}"
        )
    print("MCP servers set successfully!")


@app.command()
def set_endeavour_servers(servers: List[str], bot_id: str | None = None):
    env = get_env(bot_id)
    config = Config(endeavourServers=servers)
    data = dataclasses.asdict(
        config, dict_factory=lambda d: {k: v for k, v in d if v is not None}
    )
    response = requests.patch(
        f"{env.url}/api/bots/{env.bot_id}/config",
        json=data,
        headers=get_headers(env),
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not set Endeavour servers: {response.status_code} {response.reason}"
        )
    print("Endeavour servers set successfully!")


if __name__ == "__main__":
    app()
