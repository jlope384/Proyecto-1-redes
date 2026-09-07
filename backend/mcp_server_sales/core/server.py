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
        except TypeError:
            # A non-hashable uri (e.g. a JSON array/object instead of a string) makes each
            # module's `uri not in {...}`/`uri != CATALOG_URI` check raise TypeError instead of
            # just failing to match - treat it the same as "no module owns this uri" rather than
            # letting it crash the whole server subprocess.
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


def _params(message):
    """A valid JSON-RPC request may omit "params" or set it to anything the sender likes -
    the spec only requires it to be a structured value (object or array) when present, but
    every method here expects an object. Normalize a missing/non-dict "params" (e.g. a
    string, list, or number, all of which used to crash with an uncaught AttributeError on
    the `.get(...)` call below) to {} instead."""
    params = message.get("params")
    return params if isinstance(params, dict) else {}


def handle_message(message):
    """Given one parsed JSON-RPC request, return the response dict, or None for notifications."""
    if not isinstance(message, dict):
        # A syntactically valid JSON document that isn't a JSON-RPC request object at all
        # (e.g. a bare list/string/number) crashed with an uncaught AttributeError on
        # `message.get(...)` below instead of returning a normal protocol error. No request
        # id is recoverable from a non-object message, per the JSON-RPC 2.0 spec.
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

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
        params = _params(message)
        name = params.get("name")
        try:
            known_tool = name in DISPATCH
        except TypeError:
            # A non-hashable "name" (e.g. a JSON array/object instead of a string) makes
            # `name in DISPATCH` raise TypeError instead of just failing to match - same
            # unhashable-value crash class already fixed for resources/read's "uri", just not
            # caught here yet. Treat it as simply an unknown tool rather than crashing.
            known_tool = False
        if not known_tool:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
        # `params.get("arguments", {})` only falls back to {} when the key is absent - an
        # explicit `"arguments": null` (valid JSON-RPC) would still pass None through and
        # crash `_missing_required_arguments`'s `field not in arguments` with an uncaught
        # TypeError, so normalize any falsy value (missing or null) to {} here instead.
        result = _tool_call_result(name, params.get("arguments") or {})
    elif method == "resources/list":
        result = {"resources": _list_all_resources()}
    elif method == "resources/read":
        uri = _params(message).get("uri")
        try:
            result = {"contents": _read_any_resource(uri)}
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}
    elif method == "prompts/list":
        result = {"prompts": sales_prompts.list_prompts()}
    elif method == "prompts/get":
        params = _params(message)
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
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            # A malformed line on stdin (e.g. a client bug, or a stray non-JSON write)
            # used to raise uncaught here and kill the whole subprocess. Report it as a
            # normal JSON-RPC parse error and keep serving instead.
            error = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(error, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        response = handle_message(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
