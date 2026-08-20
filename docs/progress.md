# Development log & backlog

Course: CC3067 Redes - Proyecto 1 (MCP chatbot). Individual project, ~5 week development window.
Constraint: the MCP protocol (JSON-RPC) must be implemented by hand — no MCP SDKs (e.g. no FastMCP).

Read this file at the start of every autonomous session and update the Status section at the end.

## Status

### Done
- [x] Ollama LLM client (`backend/app/llm/ollama_client.py`) — HTTP call to `/api/chat`,
      plus `chat_raw` for tool-calling
- [x] Chat session with context history (`backend/app/chat/session.py`), incl. tool_calls/tool
      messages
- [x] Structured interaction logger (`backend/app/logging/interaction_logger.py`) — now also
      logs every MCP request/response
- [x] Interactive CLI host (`backend/app/main.py`)
- [x] MCP JSON-RPC client core (`backend/app/mcp_client/`): `initialize` handshake,
      `tools/list`, `tools/call`, `resources/list`, `resources/read`, over a stdio subprocess
      transport (`transports/stdio.py`). Hand-rolled, no MCP SDK.
- [x] Sales MCP server (`backend/mcp_server_sales/`): tools `buscar_productos`,
      `consultar_inventario`, `consultar_pedido`, `recomendar_complementos`,
      `generar_enlace_de_pago`; resources for shipping/warranty/returns policy. Hand-rolled
      JSON-RPC over stdio, mock data in `data/catalog.py`.
- [x] Chatbot wired to the sales MCP server via Ollama tool-calling (`backend/app/main.py`) —
      the LLM decides when to call a tool, the chatbot executes it through the real MCP client.
- [x] End-to-end demo script (`backend/app/demo_mcp_sales.py`) exercising the full protocol
      without the LLM in the loop.
- [x] Unit tests for the Ollama client, MCP client core (fake transport), and the sales server's
      JSON-RPC handlers (14 tests, `python -m pytest` from `backend/`)
- [x] README with setup/usage instructions

### Backlog (work in this order, roughly 3 real+tested commits per session)
1. Wire the official Filesystem MCP server (`@modelcontextprotocol/server-filesystem`
   via `npx`) into the chatbot as a callable tool, alongside the sales server.
2. Wire the official Git MCP server (`mcp-server-git`) into the chatbot. Demo scenario:
   ask the chatbot to create a repo, add a README, and commit it.
3. Write the sales server's spec doc at `docs/spec/mcp_server_sales.md` (tools, params,
   resources, example requests/responses) — required deliverable per the project brief.
4. Add a way to display the interaction log from the CLI (e.g. `python -m app.main --show-log`).
5. `mcp_server_sales` remote transport (HTTP) so the same server can run on a cloud host —
   scaffold only; actual cloud deployment is out of scope here (see below).

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
