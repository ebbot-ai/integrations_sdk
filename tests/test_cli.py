import os
import pytest
from challenger_sdk.cli import create_secret, create_env
from unittest.mock import patch


def test_missing_challenger_url():
    with pytest.raises(Exception, match="Challenger URL not present"):
        create_secret("secret", "value")


def test_missing_challenger_token():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    with pytest.raises(Exception, match="CHALLENGER_TOKEN not present"):
        create_secret("secret", "value")
    del os.environ["CHALLENGER_URL"]


def test_create_secret():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 201
        create_secret("secret", "value", "bot-id")
        mock_request.assert_called_with(
            "http://example.com/api/bots/bot-id/secrets",
            json={"name": "secret", "secret": "value"},
            headers={"Authorization": "Bearer example-token"},
        )
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]


def test_create_secret_error():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 400
        mock_request.return_value.reason = "Bad Request"
        with pytest.raises(Exception, match="Could not save secret: 400 Bad Request"):
            create_secret("secret", "value", "bot-id")
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]


def test_create_secret_bot_id_from_env():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    os.environ["BOT_ID"] = "bot-id-from-env"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 201
        create_secret("secret", "value")
        mock_request.assert_called_with(
            "http://example.com/api/bots/bot-id-from-env/secrets",
            json={"name": "secret", "secret": "value"},
            headers={"Authorization": "Bearer example-token"},
        )
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]
    del os.environ["BOT_ID"]


def test_create_secret_missing_bot_id():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    if "BOT_ID" in os.environ:
        del os.environ["BOT_ID"]
    with pytest.raises(Exception, match="Bot ID must be provided"):
        create_secret("secret", "value")
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]


def test_create_env():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 201
        create_env("env-name", "env-value", "bot-id")
        mock_request.assert_called_with(
            "http://example.com/api/bots/bot-id/env-variables",
            json={"name": "env-name", "value": "env-value"},
            headers={"Authorization": "Bearer example-token"},
        )
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]


def test_create_env_error():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 400
        mock_request.return_value.reason = "Bad Request"
        with pytest.raises(Exception, match="Could not save env variable: 400 Bad Request"):
            create_env("env-name", "env-value", "bot-id")
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]


def test_create_env_bot_id_from_env():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    os.environ["BOT_ID"] = "bot-id-from-env"
    with patch("requests.post") as mock_request:
        mock_request.return_value.status_code = 201
        create_env("env-name", "env-value")
        mock_request.assert_called_with(
            "http://example.com/api/bots/bot-id-from-env/env-variables",
            json={"name": "env-name", "value": "env-value"},
            headers={"Authorization": "Bearer example-token"},
        )
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]
    del os.environ["BOT_ID"]


def test_create_env_missing_bot_id():
    os.environ["CHALLENGER_URL"] = "http://example.com"
    os.environ["CHALLENGER_TOKEN"] = "example-token"
    if "BOT_ID" in os.environ:
        del os.environ["BOT_ID"]
    with pytest.raises(Exception, match="Bot ID must be provided"):
        create_env("env-name", "env-value")
    del os.environ["CHALLENGER_URL"]
    del os.environ["CHALLENGER_TOKEN"]
