"""Standalone demo: launches the sales MCP server and drives it through the full
protocol (initialize, tools/list, tools/call, resources/list, resources/read) using
the hand-rolled MCP client. Run with: python -m app.demo_mcp_sales
"""
from app.mcp_client.client import MCPClient
from app.mcp_client.transports.stdio import StdioTransport
from app.ui.console import render_demo_step


def run():
    transport = StdioTransport("python", ["-m", "mcp_server_sales"])
    client = MCPClient(transport, server_name="sales")

    render_demo_step("initialize", client.initialize())

    tools = client.list_tools()
    render_demo_step("tools/list", [t["name"] for t in tools])

    render_demo_step(
        "tools/call buscar_productos", client.call_tool("buscar_productos", {"query": "camisa"})
    )
    render_demo_step(
        "tools/call consultar_inventario",
        client.call_tool("consultar_inventario", {"sku": "CAM-001"}),
    )
    render_demo_step(
        "tools/call generar_enlace_de_pago",
        client.call_tool(
            "generar_enlace_de_pago", {"sku": "CAM-001", "talla": "M", "cantidad": 1}
        ),
    )

    resources = client.list_resources()
    render_demo_step("resources/list", resources)
    render_demo_step("resources/read policy://envio", client.read_resource("policy://envio"))
    render_demo_step(
        "resources/read catalog://productos", client.read_resource("catalog://productos")
    )

    client.close()


if __name__ == "__main__":
    run()
