"""Routes tool calls to the MCP client that owns them, across multiple connected servers."""
from app.mcp_client.adapters import mcp_tool_to_ollama_tool


class DuplicateToolError(ValueError):
    pass


class ToolRegistry:
    def __init__(self):
        self._clients_by_tool = {}
        self._ollama_tools = []

    def register(self, client):
        for spec in client.list_tools():
            name = spec["name"]
            if name in self._clients_by_tool:
                raise DuplicateToolError(f"Duplicate MCP tool name across servers: {name}")
            self._clients_by_tool[name] = client
            self._ollama_tools.append(mcp_tool_to_ollama_tool(spec))

    def ollama_tools(self):
        return list(self._ollama_tools)

    def client_for(self, tool_name):
        return self._clients_by_tool[tool_name]
