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


def test_tools_call_generar_enlace_de_pago_rejects_non_positive_cantidad():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 45,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "CAM-001", "talla": "M", "cantidad": -5},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "cantidad" in result["content"][0]["text"].lower()


def test_tools_call_explicit_null_arguments_returns_tool_error_not_crash():
    # `params.get("arguments", {})` only falls back to {} when the key is missing entirely -
    # an explicit `"arguments": null` (valid JSON-RPC) previously reached
    # `_missing_required_arguments`'s `field not in arguments` as a bare None, raising an
    # uncaught TypeError that killed the whole server subprocess instead of a normal tool
    # error.
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 46,
            "method": "tools/call",
            "params": {"name": "buscar_productos", "arguments": None},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "query" in result["content"][0]["text"]


def test_tools_call_consultar_inventario_returns_stock_by_size():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {"name": "consultar_inventario", "arguments": {"sku": "CAM-001"}},
        }
    )
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload == {"sku": "CAM-001", "stock_por_talla": {"S": 5, "M": 12, "L": 8, "XL": 0}}


def test_tools_call_consultar_pedido_returns_order_details():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 51,
            "method": "tools/call",
            "params": {"name": "consultar_pedido", "arguments": {"pedido_id": "PED-1001"}},
        }
    )
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["estado"] == "enviado"
    assert payload["items"][0]["sku"] == "CAM-001"


def test_tools_call_consultar_pedido_unknown_id_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 52,
            "method": "tools/call",
            "params": {"name": "consultar_pedido", "arguments": {"pedido_id": "PED-9999"}},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "PED-9999" in result["content"][0]["text"]


def test_tools_call_recomendar_complementos_returns_matching_products():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 53,
            "method": "tools/call",
            "params": {"name": "recomendar_complementos", "arguments": {"sku": "CAM-001"}},
        }
    )
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert {p["sku"] for p in payload} == {"COR-003", "CIN-004"}


def test_tools_call_recomendar_complementos_unknown_sku_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 54,
            "method": "tools/call",
            "params": {"name": "recomendar_complementos", "arguments": {"sku": "NOPE"}},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "NOPE" in result["content"][0]["text"]


def test_tools_call_generar_enlace_de_pago_returns_checkout_link():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 55,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "CAM-001", "talla": "M", "cantidad": 2},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["total"] == 498.0
    assert payload["requiere_confirmacion_cliente"] is True
    assert payload["enlace_pago"].endswith("CAM-001-M-2")


def test_tools_call_generar_enlace_de_pago_unknown_sku_returns_tool_error_not_crash():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 56,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "NOPE", "talla": "M", "cantidad": 1},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "NOPE" in result["content"][0]["text"]


def test_tools_call_generar_enlace_de_pago_rejects_quantity_over_stock():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 57,
            "method": "tools/call",
            "params": {
                "name": "generar_enlace_de_pago",
                "arguments": {"sku": "CIN-004", "talla": "UNICA", "cantidad": 1},
            },
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "Stock insuficiente" in result["content"][0]["text"]


def test_unknown_method_returns_json_rpc_error():
    response = handle_message({"jsonrpc": "2.0", "id": 5, "method": "not/a/method"})
    assert response["error"]["code"] == -32601


def test_non_dict_message_returns_invalid_request_error_not_crash():
    for message in [[1, 2, 3], "hello", 42, None]:
        response = handle_message(message)
        assert response["error"]["code"] == -32600
        assert response["id"] is None


def test_non_dict_params_does_not_crash_tools_call_resources_read_or_prompts_get():
    # "params" is present (so the earlier params.get("...", {}) fallback never kicked in)
    # but isn't an object - a string/list/number, all valid JSON, none of them a dict.
    for method in ["tools/call", "resources/read", "prompts/get"]:
        response = handle_message({"jsonrpc": "2.0", "id": 1, "method": method, "params": "not-an-object"})
        assert "error" in response or response["result"].get("isError") is True


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


def test_prompts_get_recomendar_outfit_includes_ocasion_and_presupuesto():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "prompts/get",
            "params": {
                "name": "recomendar_outfit",
                "arguments": {"ocasion": "boda", "presupuesto": "500"},
            },
        }
    )
    result = response["result"]
    text = result["messages"][0]["content"]["text"]
    assert "boda" in text
    assert "Q500" in text


def test_prompts_get_recomendar_outfit_without_optional_presupuesto():
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "prompts/get",
            "params": {"name": "recomendar_outfit", "arguments": {"ocasion": "entrevista"}},
        }
    )
    result = response["result"]
    text = result["messages"][0]["content"]["text"]
    assert "entrevista" in text
    assert "Q" not in text


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


def test_prompts_get_explicit_null_arguments_returns_json_rpc_error_not_crash():
    # Same explicit-null gap as tools/call above, for the prompts/get path.
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 47,
            "method": "prompts/get",
            "params": {"name": "resumen_pedido", "arguments": None},
        }
    )
    assert response["error"]["code"] == -32602
    assert "pedido_id" in response["error"]["message"]


def test_prompts_get_list_arguments_returns_json_rpc_error_not_crash():
    # A malformed prompts/get request with a JSON array instead of an object for "arguments"
    # used to raise an uncaught TypeError from `arguments["pedido_id"]` indexing a list.
    response = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 48,
            "method": "prompts/get",
            "params": {"name": "resumen_pedido", "arguments": ["pedido_id"]},
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


def test_resources_read_unhashable_uri_returns_json_rpc_error_not_crash():
    # A malformed resources/read request with a JSON array/object instead of a string "uri"
    # used to raise an uncaught TypeError ("unhashable type") from `uri not in POLICIES`.
    response = handle_message(
        {"jsonrpc": "2.0", "id": 15, "method": "resources/read", "params": {"uri": ["policy://envio"]}}
    )
    assert response["error"]["code"] == -32602
