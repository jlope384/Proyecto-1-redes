import threading

import pytest
import requests

from app.mcp_client.client import MCPClient
from app.mcp_client.transports.http import HttpTransport
from mcp_server_sales.core.http_server import RPC_PATH, make_server


@pytest.fixture
def http_server():
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_initialize_over_http_returns_server_info(http_server):
    response = requests.post(
        http_server + RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        timeout=5,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["serverInfo"]["name"] == "mcp-server-sales"


def test_notification_gets_202_and_no_body(http_server):
    response = requests.post(
        http_server + RPC_PATH,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=5,
    )

    assert response.status_code == 202
    assert response.content == b""


def test_unknown_path_returns_404(http_server):
    response = requests.post(http_server + "/nope", json={}, timeout=5)

    assert response.status_code == 404


def test_mcp_client_drives_full_handshake_and_tool_call_over_http(http_server):
    transport = HttpTransport(http_server)
    client = MCPClient(transport, server_name="sales")

    client.initialize()
    tools = client.list_tools()
    assert any(tool["name"] == "buscar_productos" for tool in tools)

    result = client.call_tool("buscar_productos", {"query": "camisa"})
    assert result["isError"] is False
