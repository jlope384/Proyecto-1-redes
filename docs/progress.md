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
- [x] Official Filesystem MCP server (`@modelcontextprotocol/server-filesystem`, launched via
      `npx`) wired into the chatbot as a second tool source, scoped to `backend/workspace/`.
      Added `app/mcp_client/registry.py` (`ToolRegistry`) so tool calls from the LLM route to
      whichever connected server owns that tool name, and reject duplicate tool names across
      servers. Verified end-to-end (write_file + read_text_file through the real subprocess,
      alongside a real sales-server call) and unit-tested (`tests/test_mcp_registry.py`).
- [x] Official Git MCP server (`mcp-server-git`, launched via `uvx`) wired in as a third tool
      source, operating on `backend/workspace/demo-repo/`. That server ships no `git_init` tool,
      so `app/main.py:ensure_git_repo` bootstraps the repo itself on first connect (idempotent,
      unit-tested in `tests/test_main_git_bootstrap.py` with the real `git` binary). Verified the
      full demo scenario end-to-end for real: LLM-style tool calls write a README via the
      filesystem server, then `git_add`/`git_commit`/`git_log` via the git server produce a real
      commit.
- [x] Sales server spec doc at `docs/spec/mcp_server_sales.md`: every tool and resource (params,
      JSON Schema, example requests/responses) and the error-handling model (JSON-RPC error vs.
      `isError: true` result), all verified against real server output via `demo_mcp_sales.py`.
- [x] `python -m app.main --show-log`: reads `backend/logs/interactions.log` (JSON lines) and
      prints each recorded LLM/MCP request/response. Added `format_log_entry`/`read_log_entries`/
      `show_log` in `app/main.py`, argparse-wired so `--show-log` prints the log and exits instead
      of starting the chatbot loop. Unit-tested (`tests/test_show_log.py`, 4 tests) and verified
      manually against a real generated log file.
- [x] `mcp_server_sales` HTTP transport scaffold: `core/http_server.py` exposes the exact same
      `handle_message` JSON-RPC logic (from `core/server.py`) over a single `POST /rpc` endpoint
      using only `http.server` (no MCP SDK, no web framework). `python -m mcp_server_sales
      --transport http --port 8765` runs it standalone; stdio stays the default so the chatbot in
      `app/main.py` is unaffected. Added the matching client-side `app/mcp_client/transports/http.py`
      (same `send`/`receive`/`close` interface as the stdio transport). This is a scaffold only —
      no auth, no MCP session headers, no SSE — real cloud hosting is still out of scope (see
      below). Verified for real over localhost sockets, not mocked: unit tests spin up an actual
      `ThreadingHTTPServer` on an ephemeral port and drive it both with raw HTTP requests and with
      a real `MCPClient` doing the full initialize → tools/list → tools/call handshake
      (`tests/test_mcp_server_sales_http.py`, 4 tests); also smoke-tested manually via `curl`.

### Backlog (work in this order, roughly 3 real+tested commits per session)
No items queued right now — both items from the previous backlog were completed this session.
Next planning session should add the next real increment here (e.g. resource/prompt support,
richer error surfaces, or a first pass at the report write-up) before the following autonomous
run.

### Needs verification by the student on their own machine
- Full live run of `python -m app.main` with a real Ollama server: the sandbox this session ran
  in has no `localhost:11434`, so the three-way tool routing (sales + filesystem + git) was
  verified end-to-end with real subprocesses but with the LLM call driven directly rather than
  through Ollama's tool-calling. Please run it once locally and confirm the model actually picks
  the right tool (filesystem vs. git vs. sales) from natural-language prompts.
- New local requirements as of this session: Node.js (`npx`, for the filesystem server) and
  [uv](https://docs.astral.sh/uv/) (`uvx`, for the git server), on top of Ollama. Both are already
  documented in the README.
- The git demo repo (`backend/workspace/demo-repo/`) commits using whatever `git` identity is
  configured globally on the machine running it — check `git config --global user.name/user.email`
  are set, or `git_commit` calls will fail.

### RESOLVED: the previous session's "could not push" block
An earlier session recorded a block here saying its 4 commits couldn't be pushed (403 on both
`git push` and the GitHub API write path). By the start of this session, `origin/main` already
had all of those commits — the push evidently went through after all (or access was fixed) even
though that session's transcript ended on the failure. Nothing was lost; this note is just
correcting the record. If `git push` ever rejects again with a 403 naming a GitHub App
permission gap, the fix is still: reconnect/reinstall the Claude GitHub App with write access
from claude.ai Settings → Connectors, or have an org admin grant it at
https://github.com/apps/claude/installations/select_target.

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
