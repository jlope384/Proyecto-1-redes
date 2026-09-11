import pytest

from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import (
    DuplicatePromptError,
    DuplicateToolError,
    ToolRegistry,
    UnknownPromptError,
    UnknownToolError,
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


def test_client_for_unhashable_tool_name_raises_unknown_tool_error_not_crash():
    # A malformed/hallucinated LLM tool call can put anything JSON-shaped in "name" - a list
    # or dict instead of a string made `self._clients_by_tool[tool_name]` raise an uncaught
    # TypeError ("unhashable type") instead of the KeyError this method already handles,
    # which propagated straight through handle_tool_calls's `except UnknownToolError` and
    # crashed the whole chatbot session. Same crash class already fixed for the sales
    # server's own "name"/"uri" lookups.
    registry = ToolRegistry()
    registry.register(FakeClient("sales", [{"name": "buscar_productos", "description": "d", "inputSchema": {}}]))

    with pytest.raises(UnknownToolError):
        registry.client_for(["buscar_productos"])


def test_client_for_prompt_unhashable_name_raises_unknown_prompt_error_not_crash():
    registry = ToolRegistry()
    registry.register(FakeClient("sales", [], prompts=[{"name": "resumen_pedido"}]))

    with pytest.raises(UnknownPromptError):
        registry.client_for_prompt(["resumen_pedido"])


def test_register_skips_tool_spec_missing_name_instead_of_crashing():
    # A connected server (e.g. the official filesystem/git servers, or a future remote
    # deployment) is only guaranteed to return valid JSON, not a well-formed tool spec.
    # `spec["name"]` used to raise an uncaught KeyError here, crashing the whole chatbot
    # session before it even started.
    fs = FakeClient(
        "filesystem",
        [
            {"description": "no name field at all"},
            {"name": "read_file", "description": "d", "inputSchema": {}},
        ],
    )
    registry = ToolRegistry()

    registry.register(fs)  # must not raise

    assert registry.client_for("read_file") is fs
    names = {t["function"]["name"] for t in registry.ollama_tools()}
    assert names == {"read_file"}


def test_register_skips_tool_spec_with_non_string_name_instead_of_crashing():
    fs = FakeClient("filesystem", [{"name": ["not", "a", "string"], "description": "d"}])
    registry = ToolRegistry()

    registry.register(fs)  # must not raise

    assert registry.ollama_tools() == []


def test_register_skips_prompt_spec_missing_name_instead_of_crashing():
    sales = FakeClient(
        "sales",
        [],
        prompts=[{"description": "no name field"}, {"name": "resumen_pedido"}],
    )
    registry = ToolRegistry()

    registry.register(sales)  # must not raise

    assert registry.client_for_prompt("resumen_pedido") is sales


def test_register_skips_tool_spec_that_is_not_even_a_dict_instead_of_crashing():
    # A connected server's tools/list result is only guaranteed to be valid JSON, not a list
    # of objects - a bare string/number entry in the list used to reach `spec["name"]`/
    # `spec.get("name")` and raise (TypeError on a str/int, or return the wrong thing for a
    # string that happens to support .get via duck typing it doesn't actually have).
    fs = FakeClient(
        "filesystem",
        ["not a spec at all", {"name": "read_file", "description": "d", "inputSchema": {}}],
    )
    registry = ToolRegistry()

    registry.register(fs)  # must not raise

    assert registry.client_for("read_file") is fs
    names = {t["function"]["name"] for t in registry.ollama_tools()}
    assert names == {"read_file"}


def test_register_skips_prompt_spec_that_is_not_even_a_dict_instead_of_crashing():
    sales = FakeClient("sales", [], prompts=[42, {"name": "resumen_pedido"}])
    registry = ToolRegistry()

    registry.register(sales)  # must not raise

    assert registry.client_for_prompt("resumen_pedido") is sales
