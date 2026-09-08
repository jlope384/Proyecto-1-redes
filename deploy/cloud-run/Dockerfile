# Container image for the sales MCP server (backend/mcp_server_sales), deployed to Google
# Cloud Run for assignment section 3.1.6 (remote MCP server). The server is stdlib-only
# (see backend/requirements.txt - requests/pytest/rich are client-side, not needed here),
# so the image needs no dependency install step.
#
# Build from the repo root, with this file as the Dockerfile and backend/ as the build
# context (so only the server package is copied, not app/ or tests/):
#   docker build -f deploy/cloud-run/Dockerfile -t mcp-server-sales backend
#
# Run locally to smoke-test before deploying:
#   docker run --rm -p 8765:8765 -e PORT=8765 mcp-server-sales
#   curl -X POST http://localhost:8765/rpc -H "Content-Type: application/json" \
#        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
FROM python:3.12-slim

WORKDIR /app
COPY mcp_server_sales ./mcp_server_sales

# Cloud Run sets PORT (usually 8080) and requires listening on 0.0.0.0; both are already
# the defaults in mcp_server_sales/__main__.py when unset.
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "mcp_server_sales", "--transport", "http"]
