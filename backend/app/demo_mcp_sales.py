"""Standalone demo: launches the sales MCP server and drives it through the full
protocol (initialize, tools/list, tools/call, resources/list, resources/read) using
the hand-rolled MCP client. Run with: python -m app.demo_mcp_sales
"""
from app.mcp_client.client import MCPClient
from app.mcp_client.transports.stdio import StdioTransport


def run():
    transport = StdioTransport("python", ["-m", "mcp_server_sales"])
    client = MCPClient(transport, server_name="sales")

    print("initialize ->", client.initialize())
    print()

    tools = client.list_tools()
    print("tools/list ->", [t["name"] for t in tools])
    print()

    print("tools/call buscar_productos ->", client.call_tool("buscar_productos", {"query": "camisa"}))
    print()
    print("tools/call consultar_inventario ->", client.call_tool("consultar_inventario", {"sku": "CAM-001"}))
    print()
    print(
        "tools/call generar_enlace_de_pago ->",
        client.call_tool(
            "generar_enlace_de_pago", {"sku": "CAM-001", "talla": "M", "cantidad": 1}
        ),
    )
    print()

    resources = client.list_resources()
    print("resources/list ->", resources)
    print()
    print("resources/read policy://envio ->", client.read_resource("policy://envio"))

    client.close()


if __name__ == "__main__":
    run()
