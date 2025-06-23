import typer
import requests
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))


app = typer.Typer()


@app.command()
def create_secret(name: str, secret: str, bot_id: str | None = None):
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

    headers = {"Authorization": f"Bearer {token}"}
    data = {"name": name, "secret": secret}
    response = requests.post(
        f"{url}/api/bots/{bot_id}/secrets", json=data, headers=headers
    )
    if response.status_code != 201:
        raise Exception(
            f"Could not save secret: {response.status_code} {response.reason}"
        )
    print("Secret saved successfully!")


if __name__ == "__main__":
    app()
