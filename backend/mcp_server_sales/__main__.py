"""Entry point: `python -m mcp_server_sales` runs the sales MCP server over stdio."""
from mcp_server_sales.core.server import serve

if __name__ == "__main__":
    serve()
