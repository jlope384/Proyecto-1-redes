import pytest

from app.mcp_client.registry import DuplicateToolError, ToolRegistry


class FakeClient:
    def __init__(self, server_name, tools):
        self.server_name = server_name
        self._tools = tools
        self.calls = []

    def list_tools(self):
        return self._tools

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": f"{name} called"}]}


def test_register_routes_tools_to_owning_client():
    sales = FakeClient("sales", [{"name": "buscar_productos", "description": "d", "inputSchema": {}}])
    fs = FakeClient("filesystem", [{"name": "read_file", "description": "d", "inputSchema": {}}])
    registry = ToolRegistry()
    registry.register(sales)
    registry.register(fs)

    assert registry.client_for("buscar_productos") is sales
    assert registry.client_for("read_file") is fs
    names = {t["function"]["name"] for t in registry.ollama_tools()}
    assert names == {"buscar_productos", "read_file"}


def test_register_rejects_duplicate_tool_names_across_servers():
    a = FakeClient("a", [{"name": "same", "description": "", "inputSchema": {}}])
    b = FakeClient("b", [{"name": "same", "description": "", "inputSchema": {}}])
    registry = ToolRegistry()
    registry.register(a)

    with pytest.raises(DuplicateToolError):
        registry.register(b)
