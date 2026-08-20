"""Hand-rolled JSON-RPC 2.0 / MCP server loop over stdio (no MCP SDK).

Reference: https://www.jsonrpc.org/ and
https://modelcontextprotocol.io/specification/2025-11-25
"""
import json
import sys

from mcp_server_sales.resources import policies
from mcp_server_sales.tools.sales_tools import DISPATCH, TOOL_SPECS

SERVER_NAME = "mcp-server-sales"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"


def _tool_call_result(name, arguments):
    handler = DISPATCH[name]
    try:
        value = handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
    except ValueError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}


def handle_message(message):
    """Given one parsed JSON-RPC request, return the response dict, or None for notifications."""
    method = message.get("method")
    request_id = message.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SPECS}
    elif method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        if name not in DISPATCH:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        result = _tool_call_result(name, params.get("arguments", {}))
    elif method == "resources/list":
        result = {"resources": policies.list_resources()}
    elif method == "resources/read":
        uri = message.get("params", {}).get("uri")
        try:
            result = {"contents": policies.read_resource(uri)}
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
