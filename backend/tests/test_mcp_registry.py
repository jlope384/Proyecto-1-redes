import pytest

from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import (
    DuplicatePromptError,
    DuplicateToolError,
    ToolRegistry,
    UnknownPromptError,
)


class FakeClient:
    """`prompts` defaults to `None` to simulate a server that doesn't implement prompts/list
    at all (like the official filesystem/git servers) - list_prompts() then behaves like the
    real MCPClient talking to such a server: it raises MCPProtocolError."""

    def __init__(self, server_name, tools, prompts=None):
        self.server_name = server_name
        self._tools = tools
        self._prompts = prompts
        self.calls = []

    def list_tools(self):
        return self._tools

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": f"{name} called"}]}

    def list_prompts(self):
        if self._prompts is None:
            raise MCPProtocolError(-32601, "Method not found: prompts/list")
        return self._prompts

    def get_prompt(self, name, arguments=None):
        return {"description": name, "messages": []}


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


def test_register_ignores_servers_with_no_prompts_support():
    fs = FakeClient("filesystem", [{"name": "read_file", "description": "d", "inputSchema": {}}])
    registry = ToolRegistry()

    registry.register(fs)  # must not raise even though FakeClient.list_prompts() errors

    with pytest.raises(UnknownPromptError):
        registry.client_for_prompt("anything")


def test_register_routes_prompts_to_owning_client():
    sales = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        prompts=[{"name": "resumen_pedido"}],
    )
    registry = ToolRegistry()
    registry.register(sales)

    assert registry.client_for_prompt("resumen_pedido") is sales


def test_register_rejects_duplicate_prompt_names_across_servers():
    a = FakeClient("a", [], prompts=[{"name": "same"}])
    b = FakeClient("b", [], prompts=[{"name": "same"}])
    registry = ToolRegistry()
    registry.register(a)

    with pytest.raises(DuplicatePromptError):
        registry.register(b)
