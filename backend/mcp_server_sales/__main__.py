"""Entry point: `python -m mcp_server_sales` runs the sales MCP server over stdio by
default (used when the chatbot launches it as a subprocess), or over HTTP with
`--transport http` (scaffold for running it as a standalone service later)."""
import argparse

from mcp_server_sales.core.http_server import serve_http
from mcp_server_sales.core.server import serve


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="mcp-server-sales")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP transport only")
    parser.add_argument("--port", type=int, default=8765, help="HTTP transport only")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    if args.transport == "http":
        serve_http(args.host, args.port)
    else:
        serve()
