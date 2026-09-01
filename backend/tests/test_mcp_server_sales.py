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


def test_tools_call_buscar_productos_non_string_query_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 44,
            "method": "tools/call",
            "params": {"name": "buscar_productos", "arguments": {"query": 123}},
        }
    )
    result = response["result"]
    assert result["isError"] is True


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


def test_initialize_advertises_prompts_capability():
    response = handle_message({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}})
    assert "prompts" in response["result"]["capabilities"]


def test_prompts_list_includes_both_prompts():
    response = handle_message({"jsonrpc": "2.0", "id": 8, "method": "prompts/list"})
    names = {p["name"] for p in response["result"]["prompts"]}
    assert names == {"recomendar_outfit", "resumen_pedido"}


def test_prompts_get_resumen_pedido_fills_argument():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "prompts/get",
            "params": {"name": "resumen_pedido", "arguments": {"pedido_id": "PED-1001"}},
        }
    )
    result = response["result"]
    assert "PED-1001" in result["messages"][0]["content"]["text"]


def test_prompts_get_missing_required_argument_returns_json_rpc_error():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "prompts/get",
            "params": {"name": "resumen_pedido", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32602


def test_prompts_get_unknown_prompt_returns_json_rpc_error():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "prompts/get",
            "params": {"name": "no_existe", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32602


def test_resources_read_policy():
    response = handle_message(
        {"jsonrpc": "2.0", "id": 6, "method": "resources/read", "params": {"uri": "policy://envio"}}
    )
    assert "Envios" in response["result"]["contents"][0]["text"]


def test_resources_list_includes_the_json_catalog_resource():
    response = handle_message({"jsonrpc": "2.0", "id": 12, "method": "resources/list"})
    resources_by_uri = {r["uri"]: r for r in response["result"]["resources"]}
    assert resources_by_uri["catalog://productos"]["mimeType"] == "application/json"


def test_resources_read_catalog_returns_parseable_json_matching_products():
    response = handle_message(
        {"jsonrpc": "2.0", "id": 13, "method": "resources/read", "params": {"uri": "catalog://productos"}}
    )
    content = response["result"]["contents"][0]
    assert content["mimeType"] == "application/json"
    products = json.loads(content["text"])
    assert {p["sku"] for p in products} == {"CAM-001", "PAN-002", "COR-003", "CIN-004"}


def test_resources_read_unknown_uri_returns_json_rpc_error():
    response = handle_message(
        {"jsonrpc": "2.0", "id": 14, "method": "resources/read", "params": {"uri": "policy://no-existe"}}
    )
    assert response["error"]["code"] == -32602
