"""MCP client: drives the initialize handshake and exposes tools/resources over any transport."""
from app.mcp_client.protocol import (
    MCP_PROTOCOL_VERSION,
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
        response = self.transport.receive()
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
        result = self._call("tools/list")
        return result["tools"]

    def call_tool(self, name, arguments=None):
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return result

    def list_resources(self):
        result = self._call("resources/list")
        return result["resources"]

    def read_resource(self, uri):
        result = self._call("resources/read", {"uri": uri})
        return result["contents"]

    def close(self):
        self.transport.close()
