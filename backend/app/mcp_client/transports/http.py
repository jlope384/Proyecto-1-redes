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
        # A plain requests.post() per call opens a brand new TCP+TLS connection every
        # time - confirmed directly in the Wireshark capture against the Cloud Run
        # deployment (docs/wireshark/, report section 9). A Session reuses one
        # connection (HTTP keep-alive) across the initialize/tools-list/tools-call
        # sequence a single MCPClient always makes.
        self._session = requests.Session()

    def send(self, message):
        try:
            response = self._session.post(self.url, json=message, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"MCP server at {self.url} was unreachable: {exc}") from exc
        self._pending_response = response

    def receive(self):
        response = self._pending_response
        self._pending_response = None
        if response is None or not response.content:
            # A request expects a reply; an empty body means the server (or a proxy in
            # front of it) sent no JSON-RPC message back, not a valid "no result".
            raise ConnectionError(f"MCP server at {self.url} returned an empty response body")
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectionError(
                f"MCP server at {self.url} sent a non-JSON response body: {response.text!r} ({exc})"
            ) from exc

    def close(self):
        self._session.close()
