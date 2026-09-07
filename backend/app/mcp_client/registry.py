"""Routes tool calls and prompt lookups to the MCP client that owns them, across multiple
connected servers."""
from app.mcp_client.adapters import mcp_tool_to_ollama_tool
from app.mcp_client.protocol import MCPProtocolError


class DuplicateToolError(ValueError):
    pass


class DuplicatePromptError(ValueError):
    pass


class UnknownPromptError(LookupError):
    pass


class UnknownToolError(LookupError):
    pass


class ToolRegistry:
    def __init__(self):
        self._clients_by_tool = {}
        self._clients_by_prompt = {}
        self._ollama_tools = []

    def register(self, client):
        for spec in client.list_tools():
            name = spec["name"]
            if name in self._clients_by_tool:
                raise DuplicateToolError(f"Duplicate MCP tool name across servers: {name}")
            self._clients_by_tool[name] = client
            self._ollama_tools.append(mcp_tool_to_ollama_tool(spec))
        self._register_prompts(client)

    def _register_prompts(self, client):
        # Not every connected server implements prompts/list (the official filesystem/git
        # servers don't) - that's a normal "Method not found" MCPProtocolError, not a failure.
        try:
            prompts = client.list_prompts()
        except MCPProtocolError:
            return
        for spec in prompts:
            name = spec["name"]
            if name in self._clients_by_prompt:
                raise DuplicatePromptError(f"Duplicate MCP prompt name across servers: {name}")
            self._clients_by_prompt[name] = client

    def ollama_tools(self):
        return list(self._ollama_tools)

    def client_for(self, tool_name):
        try:
            return self._clients_by_tool[tool_name]
        except (KeyError, TypeError):
            # TypeError covers a non-hashable tool_name (e.g. a JSON array/object) - the LLM's
            # tool_calls payload is external, model-generated data this project doesn't
            # control, same reasoning as the unhashable "name"/"uri" crashes already fixed in
            # mcp_server_sales. Report it as an unknown tool instead of crashing the session.
            raise UnknownToolError(f"Unknown tool: {tool_name}") from None

    def client_for_prompt(self, prompt_name):
        try:
            return self._clients_by_prompt[prompt_name]
        except (KeyError, TypeError):
            raise UnknownPromptError(f"Unknown prompt: {prompt_name}") from None
