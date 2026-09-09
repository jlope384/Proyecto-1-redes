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


def _spec_name(spec):
    """Returns spec["name"] if spec is a dict with a string "name", else None - a spec
    missing that, or that isn't even a dict, is malformed external server output that
    can't be registered, not a reason to crash startup."""
    if not isinstance(spec, dict):
        return None
    name = spec.get("name")
    return name if isinstance(name, str) else None


class ToolRegistry:
    def __init__(self):
        self._clients_by_tool = {}
        self._clients_by_prompt = {}
        self._ollama_tools = []

    def register(self, client):
        for spec in client.list_tools():
            name = _spec_name(spec)
            if name is None:
                # A connected server - including the official filesystem/git servers, which
                # are third-party code this project doesn't control, or a future remote
                # deployment reached over the network - is only guaranteed to return valid
                # JSON, not a well-formed tool spec. A tool with no usable name can't be
                # routed or called anyway, so skip it instead of crashing the whole session
                # at startup (same "don't trust external shape" reasoning already applied to
                # tools/call results, resources, and prompts elsewhere in this project).
                continue
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
            name = _spec_name(spec)
            if name is None:
                continue
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
