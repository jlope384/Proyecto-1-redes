from unittest.mock import MagicMock, patch

import pytest
import requests

from app.mcp_client.transports.http import HttpTransport


def _fake_response(content=b'{"jsonrpc": "2.0", "id": 1, "result": {}}', status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
    response.raise_for_status.return_value = None
    return response


def test_send_then_receive_returns_parsed_json():
    transport = HttpTransport("http://example.test")
    with patch("app.mcp_client.transports.http.requests.post", return_value=_fake_response()):
        transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert transport.receive() == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_send_raises_connection_error_on_network_failure():
    # A remote MCP server being unreachable (DNS failure, refused connection, timeout)
    # previously propagated a raw requests exception instead of the ConnectionError the
    # rest of the client/host code already knows how to handle.
    transport = HttpTransport("http://example.test")
    with patch(
        "app.mcp_client.transports.http.requests.post",
        side_effect=requests.exceptions.ConnectionError("refused"),
    ):
        with pytest.raises(ConnectionError):
            transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})


def test_send_raises_connection_error_on_http_error_status():
    # A 4xx/5xx from the server (or a proxy in front of it) previously raised an uncaught
    # requests.HTTPError straight out of send().
    response = _fake_response(status_code=500)
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    transport = HttpTransport("http://example.test")
    with patch("app.mcp_client.transports.http.requests.post", return_value=response):
        with pytest.raises(ConnectionError):
            transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})


def test_receive_raises_connection_error_on_empty_body():
    # Previously returned None, which crashed the caller with an uncaught TypeError
    # ("argument of type 'NoneType' is not iterable") instead of a clean ConnectionError.
    transport = HttpTransport("http://example.test")
    with patch(
        "app.mcp_client.transports.http.requests.post",
        return_value=_fake_response(content=b""),
    ):
        transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    with pytest.raises(ConnectionError):
        transport.receive()


def test_receive_raises_connection_error_on_non_json_body():
    response = _fake_response(content=b"<html>502 Bad Gateway</html>")
    response.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    transport = HttpTransport("http://example.test")
    with patch("app.mcp_client.transports.http.requests.post", return_value=response):
        transport.send({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    with pytest.raises(ConnectionError) as exc_info:
        transport.receive()
    assert "502 Bad Gateway" in str(exc_info.value)
