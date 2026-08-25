"""HTTP transport: same send/receive/close interface as StdioTransport, but talks to an
MCP server exposing a single JSON-RPC POST endpoint (see
mcp_server_sales/core/http_server.py) over the network instead of a local subprocess.
Scaffold for connecting to a server deployed on a cloud host later; request/response only,
no MCP session headers or SSE streaming.
"""
import requests


class HttpTransport:
    def __init__(self, base_url, path="/rpc"):
        self.url = base_url.rstrip("/") + path
        self._pending_response = None

    def send(self, message):
        response = requests.post(self.url, json=message, timeout=10)
        response.raise_for_status()
        self._pending_response = response

    def receive(self):
        response = self._pending_response
        self._pending_response = None
        if response is None or not response.content:
            return None
        return response.json()

    def close(self):
        pass
