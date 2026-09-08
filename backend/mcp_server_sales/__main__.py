"""Entry point: `python -m mcp_server_sales` runs the sales MCP server over stdio by
default (used when the chatbot launches it as a subprocess), or over HTTP with
`--transport http` (used both for local testing and for the Cloud Run deployment, see
deploy/cloud-run/). The HTTP host/port default to 0.0.0.0 and $PORT so the same command
works unmodified as a Cloud Run container entrypoint (Cloud Run injects PORT, usually
8080, and requires the process to listen on 0.0.0.0)."""
import argparse
import os

from mcp_server_sales.core.http_server import serve_http
from mcp_server_sales.core.server import serve


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="mcp-server-sales")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="HTTP transport only")
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PORT", 8765)), help="HTTP transport only"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    if args.transport == "http":
        serve_http(args.host, args.port)
    else:
        serve()
