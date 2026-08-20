# Development log & backlog

Course: CC3067 Redes - Proyecto 1 (MCP chatbot). Individual project, ~5 week development window.
Constraint: the MCP protocol (JSON-RPC) must be implemented by hand — no MCP SDKs (e.g. no FastMCP).

Read this file at the start of every autonomous session and update the Status section at the end.

## Status

### Done
- [x] Ollama LLM client (`backend/app/llm/ollama_client.py`) — HTTP call to `/api/chat`
- [x] Chat session with context history (`backend/app/chat/session.py`)
- [x] Structured interaction logger (`backend/app/logging/interaction_logger.py`)
- [x] Interactive CLI host (`backend/app/main.py`)
- [x] Unit tests for the Ollama client
- [x] README with setup/usage instructions

### Backlog (work in this order, roughly 3 real+tested commits per session)
1. MCP JSON-RPC core: message framing and request/response types per the spec
   (`initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`),
   implemented by hand in `backend/app/mcp_client/`.
2. MCP client stdio transport (`backend/app/mcp_client/transports/stdio.py`) that
   launches an MCP server as a subprocess and exchanges JSON-RPC messages over
   stdin/stdout.
3. Wire the official Filesystem MCP server (`@modelcontextprotocol/server-filesystem`
   via `npx`) into the chatbot as a callable tool.
4. Wire the official Git MCP server (`mcp-server-git`) into the chatbot. Demo scenario:
   ask the chatbot to create a repo, add a README, and commit it.
5. Design and implement `mcp_server_sales` (`backend/mcp_server_sales/`): tools
   `buscar_productos`, `consultar_inventario`, `consultar_pedido`,
   `recomendar_complementos`, `generar_enlace_de_pago`; resources for shipping,
   warranty and returns policy. Manual JSON-RPC over stdio, in-memory/mock data in
   `backend/mcp_server_sales/data/`. See `docs/annotated-Propuesta mcp.pdf` for the
   original use-case proposal.
6. Wire `mcp_server_sales` into the chatbot as another MCP client connection; write
   its spec doc at `docs/spec/mcp_server_sales.md`.
7. Route every MCP request/response through the existing `interaction_logger`; add a
   way to display the log from the CLI (e.g. `python -m app.main --show-log`).
8. Tests for the MCP client core and `mcp_server_sales` tool logic (mock the stdio
   transport — no live subprocess needed for unit tests).

### Explicitly OUT of scope for the autonomous routine (needs the human)
- Remote deployment of `mcp_server_sales` to Google Cloud Run / Cloudflare (needs a
  real cloud account and credentials).
- Wireshark capture and analysis (needs the student's local network/machine).
- Report sections that depend on the above (link-layer/transport analysis).
- Presentation prep.

## Working agreement for autonomous sessions
- Aim for ~3 atomic, real, tested commits per run. No filler or empty commits just to
  raise the count — every commit must be working, reviewed-by-yourself code.
- Update this file's Status section at the end of every run: move finished items to
  Done, and note anything you had to stop on.
- If a step needs credentials, secrets, or local hardware you don't have in the cloud
  sandbox, stop and note it here instead of improvising around it.
- Push to `main` when done; there is no PR review step, so keep each commit safe to
  ship on its own.
