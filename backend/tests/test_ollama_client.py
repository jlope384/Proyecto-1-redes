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
