"""Hand-rolled JSON-RPC 2.0 / MCP server loop over stdio (no MCP SDK).

Reference: https://www.jsonrpc.org/ and
https://modelcontextprotocol.io/specification/2025-11-25
"""
import json
import sys

from mcp_server_sales.prompts import sales_prompts
from mcp_server_sales.resources import catalog_resource, policies
from mcp_server_sales.tools.sales_tools import DISPATCH, TOOL_SPECS

SERVER_NAME = "mcp-server-sales"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"

TOOL_SPECS_BY_NAME = {spec["name"]: spec for spec in TOOL_SPECS}

# Each module exposes list_resources()/read_resource(uri); read_resource raises ValueError
# for a uri it doesn't own, so we can just try each in turn.
RESOURCE_MODULES = [policies, catalog_resource]


def _list_all_resources():
    resources = []
    for module in RESOURCE_MODULES:
        resources.extend(module.list_resources())
    return resources


def _read_any_resource(uri):
    for module in RESOURCE_MODULES:
        try:
            return module.read_resource(uri)
        except ValueError:
            continue
    raise ValueError(f"Recurso desconocido: {uri}")


def _missing_required_arguments(name, arguments):
    required = TOOL_SPECS_BY_NAME[name]["inputSchema"].get("required", [])
    return [field for field in required if field not in arguments]


def _tool_call_result(name, arguments):
    missing = _missing_required_arguments(name, arguments)
    if missing:
        text = f"Faltan argumentos requeridos para {name}: {', '.join(missing)}"
        return {"content": [{"type": "text", "text": text}], "isError": True}

    handler = DISPATCH[name]
    try:
        value = handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
    except ValueError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except (TypeError, KeyError, AttributeError) as exc:
        # Defensive net for malformed arguments a schema check above didn't catch
        # (e.g. wrong type for a present field) - never let a bad tool call from
        # the LLM crash the whole server subprocess. AttributeError covers a
        # present-but-wrong-type field whose handler calls a method the given
        # type doesn't have (e.g. a non-string "query" reaching str.lower()).
        return {"content": [{"type": "text", "text": f"Argumentos invalidos para {name}: {exc}"}], "isError": True}


def handle_message(message):
    """Given one parsed JSON-RPC request, return the response dict, or None for notifications."""
    method = message.get("method")
    request_id = message.get("id")

    if method == "notifications/initialized":
        return None

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SPECS}
    elif method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        if name not in DISPATCH:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        # `params.get("arguments", {})` only falls back to {} when the key is absent - an
        # explicit `"arguments": null` (valid JSON-RPC) would still pass None through and
        # crash `_missing_required_arguments`'s `field not in arguments` with an uncaught
        # TypeError, so normalize any falsy value (missing or null) to {} here instead.
        result = _tool_call_result(name, params.get("arguments") or {})
    elif method == "resources/list":
        result = {"resources": _list_all_resources()}
    elif method == "resources/read":
        uri = message.get("params", {}).get("uri")
        try:
            result = {"contents": _read_any_resource(uri)}
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}
    elif method == "prompts/list":
        result = {"prompts": sales_prompts.list_prompts()}
    elif method == "prompts/get":
        params = message.get("params", {})
        try:
            result = sales_prompts.get_prompt(params.get("name"), params.get("arguments") or {})
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
