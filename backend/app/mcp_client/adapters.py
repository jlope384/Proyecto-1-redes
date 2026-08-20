"""Adapts MCP tool specs to the tool-calling format Ollama's /api/chat expects."""


def mcp_tool_to_ollama_tool(spec):
    return {
        "type": "function",
        "function": {
            "name": spec["name"],
            "description": spec.get("description", ""),
            "parameters": spec.get("inputSchema", {"type": "object", "properties": {}}),
        },
    }
