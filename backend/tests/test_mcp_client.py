from app.mcp_client.client import MCPClient
from app.mcp_client.protocol import MCPProtocolError
import pytest


class FakeTransport:
    """Records sent messages and replays canned responses in order."""

    def __init__(self, responses):
        self.sent = []
        self._responses = list(responses)

    def send(self, message):
        self.sent.append(message)

    def receive(self):
        return self._responses.pop(0)

    def close(self):
        pass


def test_initialize_sends_handshake_and_stores_server_info():
    transport = FakeTransport(
        [{"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "sales"}}}]
    )
    client = MCPClient(transport, server_name="sales")

    result = client.initialize()

    assert result == {"serverInfo": {"name": "sales"}}
    assert transport.sent[0]["method"] == "initialize"
    assert transport.sent[1]["method"] == "notifications/initialized"
    assert "id" not in transport.sent[1]


def test_call_tool_returns_result():
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}}])
    client = MCPClient(transport, server_name="sales")

    result = client.call_tool("buscar_productos", {"query": "camisa"})

    assert result["content"][0]["text"] == "ok"
    assert transport.sent[0]["params"]["name"] == "buscar_productos"


def test_error_response_raises_mcp_protocol_error():
    transport = FakeTransport(
        [{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}]
    )
    client = MCPClient(transport, server_name="sales")

    with pytest.raises(MCPProtocolError):
        client.list_tools()
