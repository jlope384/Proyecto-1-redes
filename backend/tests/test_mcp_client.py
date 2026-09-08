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


def test_list_prompts_returns_prompts():
    transport = FakeTransport(
        [{"jsonrpc": "2.0", "id": 1, "result": {"prompts": [{"name": "resumen_pedido"}]}}]
    )
    client = MCPClient(transport, server_name="sales")

    prompts = client.list_prompts()

    assert prompts == [{"name": "resumen_pedido"}]
    assert transport.sent[0]["method"] == "prompts/list"


def test_get_prompt_sends_name_and_arguments():
    transport = FakeTransport(
        [{"jsonrpc": "2.0", "id": 1, "result": {"description": "d", "messages": []}}]
    )
    client = MCPClient(transport, server_name="sales")

    result = client.get_prompt("resumen_pedido", {"pedido_id": "PED-1001"})

    assert result == {"description": "d", "messages": []}
    assert transport.sent[0]["params"] == {
        "name": "resumen_pedido",
        "arguments": {"pedido_id": "PED-1001"},
    }


def test_call_skips_server_notifications_before_the_matching_response():
    transport = FakeTransport(
        [
            {"jsonrpc": "2.0", "method": "notifications/progress", "params": {"pct": 50}},
            {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}},
        ]
    )
    client = MCPClient(transport, server_name="sales")

    result = client.call_tool("buscar_productos", {"query": "camisa"})

    assert result["content"][0]["text"] == "ok"


def test_call_raises_on_mismatched_response_id():
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 99, "result": {}}])
    client = MCPClient(transport, server_name="sales")

    with pytest.raises(MCPProtocolError):
        client.list_tools()


def test_list_tools_defaults_to_empty_list_on_missing_key():
    # A third-party server (this project doesn't control the official filesystem/git servers'
    # code) returning a tools/list result without a "tools" key used to raise an uncaught
    # KeyError instead of just meaning "no tools".
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = MCPClient(transport, server_name="sales")

    assert client.list_tools() == []


def test_list_resources_defaults_to_empty_list_on_null_result():
    # A response with no "result" key at all makes parse_response return None, which used to
    # raise an uncaught TypeError ("'NoneType' object is not subscriptable").
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1}])
    client = MCPClient(transport, server_name="sales")

    assert client.list_resources() == []


def test_read_resource_defaults_to_empty_list_on_missing_key():
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = MCPClient(transport, server_name="sales")

    assert client.read_resource("policy://envio") == []


def test_list_prompts_defaults_to_empty_list_on_missing_key():
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1, "result": {}}])
    client = MCPClient(transport, server_name="sales")

    assert client.list_prompts() == []


def test_error_response_raises_mcp_protocol_error():
    transport = FakeTransport(
        [{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}]
    )
    client = MCPClient(transport, server_name="sales")

    with pytest.raises(MCPProtocolError):
        client.list_tools()


def test_call_raises_mcp_protocol_error_on_non_object_json_rpc_message():
    # A transport only guarantees valid JSON, not a JSON-RPC *object* - a bare number used to
    # raise an uncaught TypeError from "id" not in response instead of a normal
    # MCPProtocolError, and a bare string/list would have silently looped forever instead
    # (substring/element membership never matches "id").
    transport = FakeTransport([5])
    client = MCPClient(transport, server_name="sales")

    with pytest.raises(MCPProtocolError):
        client.list_tools()


def test_error_response_with_non_dict_error_field_still_raises_mcp_protocol_error():
    # A spec-noncompliant peer (third-party server, or a future network deployment) sending
    # a bare string/list "error" instead of an object used to raise an uncaught AttributeError
    # from error.get(...) instead of the normal MCPProtocolError.
    transport = FakeTransport([{"jsonrpc": "2.0", "id": 1, "error": "boom"}])
    client = MCPClient(transport, server_name="sales")

    with pytest.raises(MCPProtocolError):
        client.list_tools()
