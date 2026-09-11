"""MCP client: drives the initialize handshake and exposes tools/resources over any transport."""
from app.mcp_client.protocol import (
    MCP_PROTOCOL_VERSION,
    MCPProtocolError,
    build_notification,
    build_request,
    parse_response,
)

CLIENT_NAME = "proyecto1-redes-chatbot"
CLIENT_VERSION = "0.1.0"


class MCPClient:
    def __init__(self, transport, server_name):
        self.transport = transport
        self.server_name = server_name
        self._next_id = 1
        self.server_info = None

    def _call(self, method, params=None):
        request_id = self._next_id
        self._next_id += 1
        self.transport.send(build_request(request_id, method, params))
        while True:
            response = self.transport.receive()
            if not isinstance(response, dict):
                # A transport only guarantees valid JSON, not a JSON-RPC *object* - a peer we
                # don't control (a third-party server, or a network response mangled by a
                # proxy/load balancer in front of a remote deployment) could send a bare
                # scalar or array. `"id" not in response` on a non-dict either raises
                # TypeError (a number) or silently misreads substring/element membership (a
                # string/list), which could loop here forever waiting for a "matching"
                # message that never comes, instead of failing loudly.
                raise MCPProtocolError(None, f"Received a non-object JSON-RPC message: {response!r}")
            if "id" not in response:
                # Server-initiated notification (e.g. notifications/progress, logging) sent
                # unprompted between our request and its response - not a reply to us.
                continue
            if response["id"] != request_id:
                raise MCPProtocolError(
                    None,
                    f"Received response id {response['id']!r} for method {method!r}, "
                    f"expected {request_id!r}",
                )
            return parse_response(response)

    def initialize(self):
        result = self._call(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self.server_info = result
        self.transport.send(build_notification("notifications/initialized"))
        return result

    def list_tools(self):
        # `result` is whatever a connected server sent back - including the official
        # filesystem/git servers, which are third-party code this project doesn't control - so
        # don't assume the expected key is present, that "result" itself isn't null/missing, or
        # even that it's a dict at all: `(result or {}).get(...)` only guards a *falsy* result
        # (None, {}) - a truthy non-dict result (e.g. a malformed "result": "oops" or a list)
        # would still raise an uncaught AttributeError from .get() on a str/list.
        result = self._call("tools/list")
        return result.get("tools", []) if isinstance(result, dict) else []

    def call_tool(self, name, arguments=None):
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return result

    def list_resources(self):
        result = self._call("resources/list")
        return result.get("resources", []) if isinstance(result, dict) else []

    def read_resource(self, uri):
        result = self._call("resources/read", {"uri": uri})
        return result.get("contents", []) if isinstance(result, dict) else []

    def list_prompts(self):
        result = self._call("prompts/list")
        return result.get("prompts", []) if isinstance(result, dict) else []

    def get_prompt(self, name, arguments=None):
        return self._call("prompts/get", {"name": name, "arguments": arguments or {}})

    def close(self):
        self.transport.close()
