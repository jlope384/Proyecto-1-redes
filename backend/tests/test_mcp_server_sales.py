import json

from mcp_server_sales.core.server import handle_message


def test_initialize_returns_server_info():
    response = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert response["result"]["serverInfo"]["name"] == "mcp-server-sales"


def test_notifications_initialized_returns_none():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_includes_all_five_tools():
    response = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {
        "buscar_productos",
        "consultar_inventario",
        "consultar_pedido",
        "recomendar_complementos",
        "generar_enlace_de_pago",
    }


def test_tools_call_buscar_productos():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "buscar_productos", "arguments": {"query": "camisa"}},
        }
    )
    result = response["result"]
    assert result["isError"] is False
    products = json.loads(result["content"][0]["text"])
    assert products[0]["sku"] == "CAM-001"


def test_tools_call_buscar_productos_matches_words_out_of_order():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {"name": "buscar_productos", "arguments": {"query": "camisa azul"}},
        }
    )
    products = json.loads(response["result"]["content"][0]["text"])
    assert any(p["sku"] == "CAM-001" for p in products)


def test_tools_call_unknown_sku_returns_tool_error_not_protocol_error():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "consultar_inventario", "arguments": {"sku": "NOPE"}},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "NOPE" in result["content"][0]["text"]


def test_tools_call_missing_required_argument_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {"name": "consultar_inventario", "arguments": {}},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "sku" in result["content"][0]["text"]


def test_tools_call_missing_one_of_several_required_arguments():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "CAM-001", "talla": "M"},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "cantidad" in result["content"][0]["text"]


def test_tools_call_wrong_argument_type_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 43,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "CAM-001", "talla": "M", "cantidad": "dos"},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is True


def test_unknown_method_returns_json_rpc_error():
    response = handle_message({"jsonrpc": "2.0", "id": 5, "method": "not/a/method"})
    assert response["error"]["code"] == -32601


def test_resources_read_policy():
    response = handle_message(
        {"jsonrpc": "2.0", "id": 6, "method": "resources/read", "params": {"uri": "policy://envio"}}
    )
    assert "Envios" in response["result"]["contents"][0]["text"]
