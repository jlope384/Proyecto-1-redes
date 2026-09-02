from unittest.mock import MagicMock, patch

import requests

from app.llm.ollama_client import OllamaClient, OllamaConnectionError


def test_chat_returns_message_content():
    client = OllamaClient(model="test-model", base_url="http://localhost:11434")
    fake_response = MagicMock()
    fake_response.json.return_value = {"message": {"content": "hello"}}
    fake_response.raise_for_status.return_value = None

    with patch("app.llm.ollama_client.requests.post", return_value=fake_response) as mock_post:
        result = client.chat([{"role": "user", "content": "hi"}])

    assert result == "hello"
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["model"] == "test-model"
    assert sent_payload["stream"] is False


def test_chat_raw_forwards_tools_and_returns_full_message():
    client = OllamaClient(model="test-model")
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "f", "arguments": {}}}]}
    }
    fake_response.raise_for_status.return_value = None
    tools = [{"type": "function", "function": {"name": "f", "description": "d", "parameters": {}}}]

    with patch("app.llm.ollama_client.requests.post", return_value=fake_response) as mock_post:
        message = client.chat_raw([{"role": "user", "content": "hi"}], tools=tools)

    assert message["tool_calls"][0]["function"]["name"] == "f"
    assert mock_post.call_args.kwargs["json"]["tools"] == tools


def test_chat_raises_ollama_connection_error_on_network_failure():
    client = OllamaClient(model="test-model")

    with patch(
        "app.llm.ollama_client.requests.post",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ):
        try:
            client.chat([{"role": "user", "content": "hi"}])
        except OllamaConnectionError:
            return
    assert False, "expected OllamaConnectionError to be raised"


def test_chat_raw_raises_ollama_connection_error_on_invalid_json_body():
    # A 200 response whose body isn't valid JSON (e.g. Ollama crashed mid-response, or a proxy
    # returned an HTML error page with a 200 status) used to raise an uncaught JSONDecodeError
    # straight out of chat_raw instead of the documented OllamaConnectionError.
    client = OllamaClient(model="test-model")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")

    with patch("app.llm.ollama_client.requests.post", return_value=fake_response):
        try:
            client.chat_raw([{"role": "user", "content": "hi"}])
        except OllamaConnectionError:
            return
    assert False, "expected OllamaConnectionError to be raised"


def test_chat_raw_raises_ollama_connection_error_on_missing_message_key():
    # A well-formed JSON body that doesn't have the expected "message" key (e.g. an Ollama
    # error payload like {"error": "model not found"} returned with a 200 status) used to raise
    # an uncaught KeyError straight out of chat_raw instead of the documented
    # OllamaConnectionError.
    client = OllamaClient(model="test-model")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"error": "model 'test-model' not found"}

    with patch("app.llm.ollama_client.requests.post", return_value=fake_response):
        try:
            client.chat_raw([{"role": "user", "content": "hi"}])
        except OllamaConnectionError as exc:
            assert "unexpected response shape" in str(exc)
            return
    assert False, "expected OllamaConnectionError to be raised"
