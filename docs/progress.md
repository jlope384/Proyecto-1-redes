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

- [x] MCP prompts support in the sales server: hand-rolled `prompts/list`/`prompts/get`
      (`mcp_server_sales/prompts/sales_prompts.py`), two templates (`recomendar_outfit`,
      `resumen_pedido`), advertised via `capabilities.prompts` on `initialize`. Client side:
      `MCPClient.list_prompts`/`get_prompt`. Wired into the chatbot CLI as a
      `/prompt <name> key=value ...` command (`app/main.py:parse_prompt_command`/`prompt_text`)
      that fetches a prompt and starts the turn from it instead of free-typed input. Unit-tested
      server and client sides, plus the CLI parsing helpers, and verified for real against the
      actual server subprocess (not mocked).
- [x] Fixed a real crash bug: `tools/call` with a missing required argument (or one of the
      wrong type) raised an uncaught `KeyError`/`TypeError` that would have killed the whole
      `mcp-server-sales` subprocess mid-session instead of returning a normal tool error. Now
      validated against each tool's `inputSchema` before dispatch, with a defensive
      `except (TypeError, KeyError)` net around the handler call itself. Unit-tested with three
      new cases (missing single arg, missing one of several, wrong type).
- [x] `MCPClient._call` no longer assumes the next stdout line is always the reply to its own
      request: it now skips server-initiated notifications (no `id`, e.g.
      `notifications/progress`) and raises `MCPProtocolError` on a mismatched response `id`,
      instead of silently misreading either as the response. This matters for the official
      filesystem/git servers, which are free to emit notifications mid-conversation. Unit-tested
      with a fake transport that interleaves a notification before the real response, and with a
      deliberately mismatched id.
- [x] `docs/spec/mcp_server_sales.md` updated to document the new prompts capability and the
      argument-validation error behavior, keeping the spec in sync with the server it describes.

### Backlog (work in this order, roughly 3 real+tested commits per session)
- [ ] Harden `app/main.py`'s interactive loop: `handle_tool_calls` calls `client.call_tool(...)`
      with no error handling, so a transport failure (a connected MCP server subprocess dying,
      e.g. `ConnectionError` from `StdioTransport.receive`) or an `MCPProtocolError` currently
      crashes the whole chatbot session instead of reporting the failure and continuing. The
      `--show-log`/Ollama-connection path already handles this correctly (see the
      `OllamaConnectionError` handling in `run()`) — do the same for tool calls: catch, log,
      print an `[error]` line, feed a tool-error message back into the session so the LLM can
      react, and keep the loop alive.
- [ ] Consider generalizing `ToolRegistry` (currently tools-only) to also route `prompts/list`
      across multiple servers with prompts, once a second server exposes any — not needed yet
      since only `mcp-server-sales` has prompts right now, but the single-server assumption in
      `app/main.py`'s `/prompt` command (hardcoded to `sales_client`) will need revisiting then.
- [ ] Next real increment beyond that: richer resource content types (today every resource is
      `text/plain`), or a first pass at the report write-up (`docs/report/` is still empty).

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
- The new `/prompt <name> key=value ...` chatbot command was verified for real against the
  `mcp-server-sales` subprocess directly (`prompts/list`/`prompts/get` over real stdio), but not
  through the actual interactive `python -m app.main` loop with a live Ollama model, for the same
  sandbox reason as above. Please try `/prompt resumen_pedido pedido_id=PED-1001` and
  `/prompt recomendar_outfit ocasion=boda presupuesto=500` once locally and confirm the model
  picks up the injected prompt text and calls the right tools in response.

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
