import logging

from app.chat.session import ChatSession
from app.main import handle_tool_calls
from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import ToolRegistry


class FakeClient:
    def __init__(self, server_name, tools, result=None, error=None):
        self.server_name = server_name
        self._tools = tools
        self._result = result
        self._error = error
        self.calls = []

    def list_tools(self):
        return self._tools

    def list_prompts(self):
        raise MCPProtocolError(-32601, "Method not found: prompts/list")

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        if self._error is not None:
            raise self._error
        return self._result


def make_registry(client):
    registry = ToolRegistry()
    registry.register(client)
    return registry


def tool_call(name, arguments):
    return {"function": {"name": name, "arguments": arguments}}


def test_handle_tool_calls_adds_tool_result_on_success():
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "text", "text": "3 productos encontrados"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-ok")

    handle_tool_calls(registry, [tool_call("buscar_productos", {"query": "camisa"})], session, logger)

    assert session.messages[-1] == {
        "role": "tool",
        "name": "buscar_productos",
        "content": "3 productos encontrados",
    }


def test_handle_tool_calls_survives_mcp_protocol_error(capsys):
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        error=MCPProtocolError(-32602, "Invalid params"),
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-protocol-error")

    handle_tool_calls(registry, [tool_call("buscar_productos", {})], session, logger)

    assert session.messages[-1]["role"] == "tool"
    assert "Invalid params" in session.messages[-1]["content"]
    assert "[error]" in capsys.readouterr().out


def test_handle_tool_calls_survives_connection_error_and_keeps_processing_remaining_calls(capsys):
    client = FakeClient(
        "filesystem",
        [{"name": "read_file", "description": "d", "inputSchema": {}}],
        error=ConnectionError("MCP server closed stdout unexpectedly. stderr: boom"),
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-connection-error")

    handle_tool_calls(
        registry,
        [tool_call("read_file", {"path": "a.txt"}), tool_call("read_file", {"path": "b.txt"})],
        session,
        logger,
    )

    tool_messages = [m for m in session.messages if m["role"] == "tool"]
    assert len(tool_messages) == 2
    assert all("MCP server closed stdout unexpectedly" in m["content"] for m in tool_messages)
    assert capsys.readouterr().out.count("[error]") == 2


def test_handle_tool_calls_survives_unknown_tool_name(capsys):
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-unknown-tool")

    handle_tool_calls(registry, [tool_call("herramienta_inexistente", {})], session, logger)

    assert session.messages[-1]["role"] == "tool"
    assert "Unknown tool" in session.messages[-1]["content"]
    assert "[error]" in capsys.readouterr().out
    assert client.calls == []


def test_handle_tool_calls_logs_error_entry():
    logged = []

    class RecordingLogger:
        def info(self, message):
            logged.append(message)

    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        error=MCPProtocolError(-32602, "Invalid params"),
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = RecordingLogger()

    handle_tool_calls(registry, [tool_call("buscar_productos", {})], session, logger)

    assert any('"direction": "error"' in entry for entry in logged)
