import app.main as main
from app.logging.interaction_logger import build_interaction_logger
from app.mcp_client.transports.http import HttpTransport
from app.mcp_client.transports.stdio import StdioTransport


class FakeClient:
    """Stands in for MCPClient: records which transport it was built with instead of
    actually spawning a subprocess or making a network call."""

    def __init__(self, transport, server_name):
        self.transport = transport
        self.server_name = server_name

    def initialize(self):
        return {"serverInfo": {"name": "mcp-server-sales"}}


def test_connect_sales_mcp_server_uses_stdio_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("SALES_MCP_URL", raising=False)
    monkeypatch.setattr(main, "MCPClient", FakeClient)
    logger = build_interaction_logger(log_dir=str(tmp_path))

    client = main.connect_sales_mcp_server(logger)

    assert isinstance(client.transport, StdioTransport)


def test_connect_sales_mcp_server_uses_http_when_sales_mcp_url_is_set(monkeypatch, tmp_path):
    monkeypatch.setenv("SALES_MCP_URL", "https://mcp-server-sales.example.run.app")
    monkeypatch.setattr(main, "MCPClient", FakeClient)
    logger = build_interaction_logger(log_dir=str(tmp_path))

    client = main.connect_sales_mcp_server(logger)

    assert isinstance(client.transport, HttpTransport)
    assert client.transport.url == "https://mcp-server-sales.example.run.app/rpc"
