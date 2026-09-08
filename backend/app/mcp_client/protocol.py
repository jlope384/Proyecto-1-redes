"""Hand-rolled JSON-RPC 2.0 / MCP message construction and parsing (no MCP SDK).

Reference: https://www.jsonrpc.org/ and
https://modelcontextprotocol.io/specification/2025-11-25
"""

MCP_PROTOCOL_VERSION = "2025-11-25"
JSONRPC_VERSION = "2.0"


class MCPProtocolError(RuntimeError):
    """Raised when a peer returns a JSON-RPC error object."""

    def __init__(self, code, message, data=None):
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


def build_request(request_id, method, params=None):
    message = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def build_notification(method, params=None):
    message = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        message["params"] = params
    return message


def parse_response(message):
    """Return the `result` of a JSON-RPC response, raising MCPProtocolError on `error`."""
    if "error" in message:
        error = message["error"]
        # The JSON-RPC spec requires `error` to be an object, but a peer we don't control
        # (the official filesystem/git servers, or any future remote deployment reached over
        # the network) is free to send something else - a bare string, say. `error.get(...)`
        # on a non-dict used to raise an uncaught AttributeError here instead of the
        # MCPProtocolError callers already know how to handle.
        if not isinstance(error, dict):
            raise MCPProtocolError(None, str(error))
        raise MCPProtocolError(error.get("code"), error.get("message"), error.get("data"))
    return message.get("result")
