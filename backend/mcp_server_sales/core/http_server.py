"""HTTP transport for the sales MCP server: exposes the exact same hand-rolled JSON-RPC
handler (`handle_message`, from `core/server.py`) over a single POST endpoint instead of
stdio, so the server can eventually be reached over a network instead of only launched as
a local subprocess. This is a scaffold for a future cloud deployment (Cloud Run, etc.) —
that deployment itself is out of scope for the autonomous sandbox this was written in, see
docs/progress.md. Stdlib only (`http.server`), no MCP SDK, matching the project's constraint.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mcp_server_sales.core.server import handle_message

RPC_PATH = "/rpc"


class JsonRpcRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path != RPC_PATH:
            self.send_error(404, "Unknown path")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        response = handle_message(message)
        if response is None:
            self.send_response(202)
            self.end_headers()
            return

        payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def make_server(host="127.0.0.1", port=0):
    """port=0 lets the OS pick a free port; read it back via server.server_address."""
    return ThreadingHTTPServer((host, port), JsonRpcRequestHandler)


def serve_http(host="127.0.0.1", port=8765):
    server = make_server(host, port)
    bound_host, bound_port = server.server_address
    print(f"mcp-server-sales listening over HTTP on http://{bound_host}:{bound_port}{RPC_PATH}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
