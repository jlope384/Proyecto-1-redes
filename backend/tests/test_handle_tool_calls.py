import logging

from app.chat.session import ChatSession
from app.main import extract_tool_result_text, handle_tool_calls
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


def test_handle_tool_calls_adds_tool_result_on_success(capsys):
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
    assert "3 productos encontrados" in capsys.readouterr().out


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


def test_handle_tool_calls_survives_empty_content_result(capsys):
    # A real MCP server is free to return an empty `content` list (nothing in the MCP spec
    # guarantees at least one item) - `result["content"][0]` would raise IndexError and crash
    # the whole chatbot session before this was fixed.
    client = FakeClient(
        "filesystem",
        [{"name": "read_file", "description": "d", "inputSchema": {}}],
        result={"content": []},
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-empty-content")

    handle_tool_calls(registry, [tool_call("read_file", {"path": "a.txt"})], session, logger)

    assert session.messages[-1]["role"] == "tool"
    assert "no content" in session.messages[-1]["content"]


def test_handle_tool_calls_survives_non_text_content_result(capsys):
    # A content item that isn't `type: text` (e.g. an image, per the MCP spec) has no "text"
    # key - `result["content"][0]["text"]` would raise KeyError before this was fixed.
    client = FakeClient(
        "filesystem",
        [{"name": "read_image", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "image", "data": "base64...", "mimeType": "image/png"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-non-text-content")

    handle_tool_calls(registry, [tool_call("read_image", {"path": "a.png"})], session, logger)

    assert session.messages[-1]["role"] == "tool"
    assert "image" in session.messages[-1]["content"]


def test_handle_tool_calls_survives_tool_call_missing_arguments_key(capsys):
    # Ollama's tool-calling format is expected to always include "arguments", but the model
    # is an external, uncontrolled system - a malformed/truncated generation missing the key
    # entirely used to raise an uncaught KeyError and kill the whole session before this was
    # fixed, the same way a missing "content" item or a hallucinated tool name already did.
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "text", "text": "3 productos encontrados"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-missing-arguments")

    handle_tool_calls(registry, [{"function": {"name": "buscar_productos"}}], session, logger)

    assert client.calls == [("buscar_productos", {})]
    assert session.messages[-1]["role"] == "tool"


def test_handle_tool_calls_survives_tool_call_missing_function_key(capsys):
    registry = make_registry(
        FakeClient("sales", [{"name": "buscar_productos", "description": "d", "inputSchema": {}}])
    )
    session = ChatSession()
    logger = logging.getLogger("test-handle-tool-calls-missing-function")

    handle_tool_calls(registry, [{}], session, logger)

    assert "[error]" in capsys.readouterr().out
    assert session.messages == []


def test_extract_tool_result_text_joins_multiple_text_items():
    result = {"content": [{"type": "text", "text": "linea 1"}, {"type": "text", "text": "linea 2"}]}
    assert extract_tool_result_text(result) == "linea 1\nlinea 2"


def test_extract_tool_result_text_missing_content_key():
    assert extract_tool_result_text({}) == "[tool returned no content]"


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
