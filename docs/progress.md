# Development log & backlog

Course: CC3067 Redes - Proyecto 1 (MCP chatbot). Individual project, ~5 week development window.
Constraint: the MCP protocol (JSON-RPC) must be implemented by hand — no MCP SDKs (e.g. no FastMCP).

Read this file at the start of every autonomous session and update the Status section at the end.

## Status

### Done
- [x] Remote deployment of `mcp_server_sales` to Google Cloud Run — this was the one item
      genuinely blocked on the student's own cloud account/credentials, done with the
      student present in this session: installed the Google Cloud SDK, authenticated as
      the student's account, created a dedicated project (`proyecto1-redes-mcp`), linked
      billing (required by Cloud Run even for free-tier usage — no billing account existed
      on this Google account before this session, the student created one), enabled the
      Cloud Run/Artifact Registry APIs, built the existing `deploy/cloud-run/Dockerfile`
      image, pushed it to Artifact Registry, and deployed to Cloud Run. Live at
      `https://mcp-server-sales-715967091740.us-central1.run.app`, unauthenticated
      (`--allow-unauthenticated`, acceptable for this course project's scope but noted as a
      real caveat in the spec doc). Code changes to support this: `connect_sales_mcp_server`
      (`app/main.py`) now reads `SALES_MCP_URL` and switches from `StdioTransport` to the
      already-existing `HttpTransport` when set (2 new tests,
      `tests/test_connect_sales_mcp_server.py`); `mcp_server_sales/__main__.py`'s HTTP
      transport now defaults host/port to `0.0.0.0`/`$PORT` (env vars) instead of
      `127.0.0.1`/`8765`, matching what Cloud Run requires, with CLI flags still able to
      override. Verified for real, not just locally: built and ran the image in Docker
      locally first (curl against `/rpc`), then against the live Cloud Run URL both with
      `curl` (`initialize`, `tools/call buscar_productos`) and by running the actual
      `app.main.connect_sales_mcp_server` + real `MCPClient`/`HttpTransport` code path
      against the deployed service (not mocked) — both returned correct results. Full test
      suite (131 tests) still passes. Documented in `README.md` and
      `docs/spec/mcp_server_sales.md` (new "Remote deployment" section with redeploy
      commands). This unblocks the Wireshark capture (needed a real remote deployment to
      capture traffic against) and report sections 9/10 — see backlog below, now
      unblocked.
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
- [x] Hardened `app/main.py`'s interactive loop: `handle_tool_calls` now catches
      `MCPProtocolError`/`ConnectionError` around `client.call_tool(...)` instead of letting
      either crash the whole session. It logs an `"error"` interaction entry, prints an
      `[error]` line, and feeds a tool-error message back into the chat session (as a normal
      `role: tool` message) so the LLM can react and the loop keeps running. Unit-tested
      (`tests/test_handle_tool_calls.py`) with a fake client raising both exception types,
      including a case with two tool calls in one turn where the first fails and the second
      still runs.
- [x] Added a JSON resource to the sales server: `catalog://productos` (`application/json`,
      full product catalog), alongside the existing `text/plain` policy resources. `core/server.py`
      now aggregates `resources/list`/`resources/read` across a list of resource modules
      (`resources/policies.py`, the new `resources/catalog_resource.py`) instead of hardcoding
      the policies module, so adding another resource module later is a one-line change.
      Unit-tested and verified for real via `demo_mcp_sales.py` against the actual server
      subprocess; documented in `docs/spec/mcp_server_sales.md`.
- [x] Generalized `ToolRegistry` to also route MCP prompts, not just tools, across multiple
      connected servers: `register()` now calls `client.list_prompts()` and records which
      client owns each prompt name, treating a server that doesn't implement `prompts/list`
      (an `MCPProtocolError` "Method not found") as simply having no prompts rather than a
      failure. `app/main.py`'s `/prompt` command now resolves the owning client via
      `registry.client_for_prompt(name)` instead of a hardcoded reference to `sales_client`.
      Unit-tested, and verified for real against both the sales server subprocess (prompt
      routes correctly, `get_prompt` returns real content) and the official filesystem MCP
      server subprocess (registration doesn't crash on its missing prompts support).
- [x] Fixed a second real crash bug, found via a code-review pass (see note below): the LLM
      calling a tool name no connected server exposes (a hallucination, or a typo it made up)
      raised a raw `KeyError` from `ToolRegistry.client_for` that `handle_tool_calls` did not
      catch, killing the whole chatbot session. Added `UnknownToolError` in
      `app/mcp_client/registry.py`, handled in `handle_tool_calls` the same way as the existing
      `MCPProtocolError`/`ConnectionError` cases. Unit-tested
      (`tests/test_handle_tool_calls.py`).
- [x] The chatbot now supports chaining multiple tool calls within a single user turn (e.g.
      "search for a product, then check its stock"), instead of only one round: the follow-up
      call after a tool result previously omitted the `tools` list entirely, so the model could
      not request a second tool even when it needed to. Extracted `run_turn()` in `app/main.py`,
      which loops (offering tools every round) until the LLM answers with plain text or
      `MAX_TOOL_ROUNDS` (5) is reached; also fixed a related gap where an Ollama connection
      failure on a follow-up round would have propagated uncaught instead of being reported like
      a first-round failure. Unit-tested with a mocked LLM client
      (`tests/test_run_turn.py`): plain reply, two chained tool-call rounds, hitting the round
      cap, and connection failures on both the first and a later round.
- [x] Filled real gaps in `README.md` found in the same review pass: it only showed
      Windows-style venv activation and env-var syntax (no Linux/macOS equivalent), and never
      documented the `/prompt <name> key=value ...` command or the git-identity requirement for
      the git MCP demo (previously only noted in this file). Added all three, plus a usage
      example for the new chained-tool-calls behavior.
- [x] First pass at the report write-up: `docs/report/informe.md` created with an
      introductory section on MCP's background (why the protocol exists, the three actors —
      server/client/host — mapped to this project's actual modules, and the request/
      notification/response shapes of JSON-RPC as used here) and section 8 (spec of the three
      MCP servers the chatbot connects to: the hand-rolled `mcp_server_sales`, pointing at the
      existing `docs/spec/mcp_server_sales.md` instead of duplicating it, plus the official
      filesystem/git servers' launch commands, scoping, and the tools exercised in the
      end-to-end demo scenario). Sections 9 and 10 are explicitly left for later — see backlog.

- [x] Finished the three follow-ups this session left open on the 15%-extra-credit terminal UI:
      (1) Tool call results are now shown to the user, not just fed to the LLM: added
      `render_tool_result` (`app/ui/console.py`), same dim-yellow/low-visual-weight styling as
      the existing "-> calling tool" line, truncated to 200 chars so a large payload (e.g. the
      `catalog://productos` resource) can't flood the terminal. Wired into `handle_tool_calls`
      right after a successful `call_tool`. Unit-tested (new cases in `tests/test_ui_console.py`
      and an updated case in `tests/test_handle_tool_calls.py` asserting the result text reaches
      stdout), and verified for real under a pseudo-tty (correct dim-yellow ANSI codes).
      (2) Reviewed readability/wrapping on a real narrow terminal: ran the banner, a tool call +
      result, a bot reply panel, and an error line under `script -qc ...` with `COLUMNS=40`. Both
      `Panel`s (banner, bot reply) wrap their text cleanly inside the box; the plain tool-call/
      result/error lines word-wrap at the console width with no crash. Long unbreakable tokens
      (e.g. a checkout URL) fold mid-word, which is normal terminal-wrapping behavior, not a
      defect - no code change needed here, this was a real check that came back clean.
      (3) Decided the same `rich` treatment IS worth a light-touch version for
      `app/demo_mcp_sales.py`, unlike `show_log` (which stays plain because it's meant to be
      piped/grepped): this script is read directly by a person exercising the protocol by hand,
      so added `render_demo_step` (bold blue label per JSON-RPC step, e.g. `tools/call
      buscar_productos ->`) while leaving the raw response payload after it exactly as Python
      prints it - no reformatting, no truncation, since showing the real complete server
      response is the whole point of the script. Unit-tested and verified for real against the
      actual `mcp_server_sales` subprocess (`python -m app.demo_mcp_sales`).
- [x] Started the 15%-extra-credit terminal UI (backlog item raised by the previous session,
      assignment section 4.1): `backend/app/ui/console.py` renders the chatbot host through
      `rich` instead of undifferentiated `print()`. Fixed color convention chosen for visual
      hierarchy and standard color psychology: cyan for the user's own prompt, green for the
      bot's actual reply (boxed in its own panel so it stands out from the surrounding log),
      dim yellow for secondary/background MCP tool-call activity (now also visibly announced
      before it runs, which previously happened silently), bold red for errors, blue for the
      startup banner/system info. Wired into `app/main.py`'s interactive loop and
      `handle_tool_calls`/`run_turn`, replacing every plain `print()` there (deliberately left
      `show_log`'s output as plain text - it's meant to be pipeable/greppable, so colorizing it
      would work against that use case rather than for it). Also added a `render_thinking`
      status spinner around the LLM call in `run_turn`, since the CLI previously gave zero
      feedback between hitting enter and the reply appearing (a real "visibility of system
      status" usability gap given how slow a local Ollama call can be). Unit-tested
      (`tests/test_ui_console.py`, 8 tests, rendering into an in-memory `rich.Console` and
      asserting on the plain-text content) and verified for real under an actual pseudo-tty
      (`script -qc ...`), confirming the ANSI color codes are emitted correctly (blue banner,
      green bot panel, dim yellow tool-call line, bold red error) - not just that it degrades
      gracefully to plain text under pytest's captured, non-tty stdout. `rich>=13.7` added to
      `backend/requirements.txt`. Documented in the top-level `README.md`.

- [x] Re-checked both remaining backlog items at the start of this session (report sections 9/10,
      and the optional binary resource): both still genuinely blocked on the same things as
      before (a live Wireshark capture against a *remote* deployment that doesn't exist yet, and
      no real use case for a binary resource in the sales server's scope) — nothing to implement
      there, so this session did a focused code-review pass over the whole `backend/` tree
      instead (client, both servers, transports, host loop) looking for real crash/robustness
      bugs, the same kind of work earlier sessions did when they found and fixed the
      hallucinated-tool-name and tool-call-chaining bugs. Found and fixed four, each with a
      regression test that fails against the pre-fix code and passes after:
      1. `buscar_productos` raised an uncaught `AttributeError` (not caught by the existing
         `except (TypeError, KeyError)` net) on a non-string `query` argument (e.g. `{"query":
         123}`, plausible from an LLM's JSON tool-call arguments), which crashed the whole
         `mcp-server-sales` subprocess for the rest of the session. Widened the except clause to
         also catch `AttributeError`.
      2. `generar_enlace_de_pago` only checked `cantidad > stock`, so `cantidad <= 0` (e.g. -5)
         always passed regardless of stock and produced a "confirmed" payment link with a
         negative total. Added an explicit positive-quantity check.
      3. `StdioTransport.receive()` let a `json.JSONDecodeError` propagate uncaught if a server
         subprocess ever wrote a non-JSON line to stdout (e.g. a first-run banner from a server
         launched via `npx`/`uvx`, which share that same stream with the JSON-RPC protocol) -
         now raises a normal `ConnectionError` instead, same as the existing closed-stdout case.
         `StdioTransport.close()` let `subprocess.TimeoutExpired` propagate if a server ignored
         `terminate()`, which (uncaught by `app/main.py`'s per-client cleanup loop) would skip
         closing every other already-connected server after it - now kills the process instead.
         No test file existed for `StdioTransport` before this session; added
         `tests/test_stdio_transport.py` against a mocked subprocess (6 tests).
      4. In `app/main.py:run()`, all three MCP servers were connected and registered *before*
         the `try/finally` that closes them, so if one server failed to start or register after
         another had already spawned successfully, the earlier subprocess was never terminated.
         Extracted `connect_mcp_servers()` (closes every client connected so far and re-raises
         on a later failure) and moved registration inside the existing `try/finally`.
         Unit-tested with fake connectors/clients (`tests/test_connect_mcp_servers.py`, 3 tests).
      All four verified against the real `mcp_server_sales` subprocess via
      `python -m app.demo_mcp_sales` after the fixes (still runs correctly end-to-end), plus the
      full suite (84 tests, up from 73 at the start of this session, all passing).
- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — nothing new to implement there,
      so this session did another focused code-review pass over `backend/` and found and fixed
      two more real, previously-untested crash bugs:
      1. `handle_tool_calls` (`app/main.py`) read a `tools/call` result as
         `result["content"][0]["text"]` unconditionally. Nothing in the MCP spec guarantees a
         non-empty `content` list or that every item is `type: text` — a server is free to
         return `content: []`, or a non-text item like an `image` (the official filesystem/git
         servers are third-party code, not something this project controls). Either shape raised
         an uncaught `IndexError`/`KeyError` that killed the whole chatbot session. Added
         `extract_tool_result_text()`: joins all `text`-type content items, and falls back to a
         descriptive placeholder (naming the content type, or "no content") instead of crashing.
         Unit-tested with an empty-content result and a non-text (`image`) result
         (`tests/test_handle_tool_calls.py`), plus direct tests of the new helper.
      2. `OllamaClient.chat_raw` (`app/llm/ollama_client.py`) called `response.json()["message"]`
         *outside* the `try/except` that catches request/connection failures, with no check that
         the `"message"` key exists. A 200 response with a non-JSON body, or a well-formed but
         unexpected JSON shape (e.g. an Ollama error payload like `{"error": "model not found"}`
         returned with a 200 status instead of the expected 4xx), raised an uncaught
         `JSONDecodeError`/`KeyError` straight out of `chat_raw` instead of the documented
         `OllamaConnectionError` that `run_turn` relies on to keep the session alive after an LLM
         failure. Fixed by moving `response.json()` inside the `try` (catching `ValueError` for
         a non-JSON body) and explicitly checking for the `"message"` key before returning it.
         Unit-tested per the existing mocked-LLM-call pattern (`tests/test_ollama_client.py`):
         invalid JSON body, and a JSON body missing `"message"`.
      Both verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite (90 tests, up
      from 84 at the start of this session, all passing). Neither fix could be exercised through
      a live `python -m app.main` + real Ollama session in this sandbox, for the usual reason
      (no `localhost:11434` here) — see "Needs verification" below.

- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — nothing new to implement
      there, so this session did another focused code-review pass over `backend/`,
      specifically the parts of the client/server stack the two previous review sessions
      hadn't looked at as closely (the HTTP transport scaffold, and the JSON-RPC argument
      normalization in `mcp_server_sales/core/server.py`). Found and fixed two more real,
      previously-untested crash bugs:
      1. `HttpTransport` (`app/mcp_client/transports/http.py`) let a `requests` network
         failure (connection refused, timeout) or a 4xx/5xx status from `raise_for_status()`
         propagate as an uncaught `requests.exceptions.RequestException`/`HTTPError` out of
         `send()`, and `receive()` silently returned `None` on an empty response body
         instead of raising — which then crashed the caller (`MCPClient._call`) with an
         uncaught `TypeError` ("argument of type 'NoneType' is not iterable") rather than
         the `ConnectionError` the rest of the client/host code already knows how to handle
         (same contract `StdioTransport` already follows: `receive()` either returns a
         parsed dict or raises `ConnectionError`, never `None`). This only matters once the
         HTTP scaffold is used against a real network (the remote deployment, still
         pending), so it hadn't been exercised by the existing real-socket HTTP tests,
         which never hit a network failure or an empty body. Fixed `send()`/`receive()` to
         catch `requests.exceptions.RequestException` and empty/non-JSON bodies and raise
         `ConnectionError` instead. 5 new unit tests
         (`tests/test_http_transport.py`, mocking `requests.post`), plus the existing
         real-socket HTTP tests (`tests/test_mcp_server_sales_http.py`) still pass.
      2. `mcp_server_sales/core/server.py`'s `handle_message`: both the `tools/call` and
         `prompts/get` branches read `params.get("arguments", {})`, which only falls back
         to `{}` when the `"arguments"` key is *absent* — a valid JSON-RPC request with an
         explicit `"arguments": null` passed a bare `None` through to
         `_missing_required_arguments`'s `field not in arguments` check, raising an
         uncaught `TypeError` that crashed the whole `mcp-server-sales` subprocess, instead
         of the normal validation error both paths already return for a missing/empty
         arguments object. Our own `MCPClient`/host never sends an explicit null (it already
         normalizes with `arguments or {}` on the client side), so this wasn't reachable
         through the chatbot itself, but the server is a standalone JSON-RPC endpoint any
         MCP-compliant client could call, and the assignment specifically asks for manual,
         spec-correct protocol handling. Fixed both branches to normalize with
         `params.get("arguments") or {}`. Two new regression tests in
         `tests/test_mcp_server_sales.py`.
      Both verified against the real `mcp_server_sales` subprocess via
      `python -m app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite
      (97 tests, up from 90 at the start of this session, all passing). Neither fix could be
      exercised through a live `python -m app.main` + real Ollama session in this sandbox,
      for the usual reason (no `localhost:11434` here).

- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — nothing new to implement
      there, so this session did another focused code-review pass over `backend/` (via a
      dedicated review agent covering the parts of the stack prior sessions' passes hadn't
      focused on as closely: `app/chat/session.py`, `app/logging/interaction_logger.py`,
      `mcp_server_sales/prompts/sales_prompts.py`, `mcp_server_sales/resources/*.py`,
      `app/main.py`'s prompt-parsing and `--show-log` helpers, and `app/mcp_client/client.py`'s
      handling of `tools/list`/`resources/list`/`resources/read`/`prompts/list` results).
      Found and fixed four more real, previously-untested bugs, each with a regression test
      verified to fail against the pre-fix code and pass after:
      1. `mcp_server_sales/prompts/sales_prompts.py`'s `get_prompt` had no defensive except net
         (unlike `tools/call`'s `_tool_call_result`), so a malformed `prompts/get` request with
         `"arguments"` as a JSON array instead of an object (e.g. `["pedido_id"]"`, which passes
         the naive `field not in arguments` membership check) raised an uncaught `TypeError`
         from indexing a list and crashed the whole `mcp-server-sales` subprocess. Added the
         same kind of `except (TypeError, KeyError, AttributeError)` net tools/call already has.
      2. `mcp_server_sales/core/server.py`'s `resources/read` path (via
         `resources/policies.py`'s dict-membership check) raised an uncaught `TypeError`
         ("unhashable type") on a non-string `uri` (e.g. a JSON array/object), crashing the
         subprocess instead of returning a normal JSON-RPC error. `_read_any_resource` now
         also catches `TypeError`, same as it already did for `ValueError`.
      3. `app/mcp_client/client.py`'s `list_tools`/`list_resources`/`read_resource`/
         `list_prompts` all unconditionally indexed the result dict (e.g. `result["tools"]`) —
         the same crash class already fixed for `tools/call` results in an earlier session, but
         never extended to these. A connected server — including the official filesystem/git
         servers, which are third-party code this project doesn't control — returning a result
         missing the expected key (or no result at all) raised an uncaught `KeyError`/`TypeError`
         during `ToolRegistry.register()` at startup. Now defaults to an empty list in each case.
      4. `app/main.py`'s `parse_prompt_command` used a plain `text.startswith("/prompt")`, which
         also matched an ordinary chat message that merely starts with those 7 characters (e.g.
         "/prompted the wrong SKU, can you check?"), misparsing it as a prompt command named
         "prompted" and silently swallowing the rest of the user's actual message. Now requires
         the literal command word (`/prompt` alone, or followed by a space).
      Also fixed a fifth bug found in the same pass, in `app/main.py`'s `--show-log` path:
      `read_log_entries` called `json.loads` on every non-blank line with no guard, so a single
      truncated/corrupted log line (e.g. the logger process killed mid-write) raised an
      uncaught `JSONDecodeError` and hid every valid entry recorded before and after it. Now
      yields a visible placeholder entry for that line instead of crashing. Verified manually
      against a real corrupted log file, not just the unit test.
      All five verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite (105 tests, up
      from 97 at the start of this session, all passing).
      Not fixed this session (noted for later, low priority): the review also flagged that
      `app/logging/interaction_logger.py`'s `build_interaction_logger` uses a
      `logging.getLogger(name)` singleton guarded by `if not logger.handlers`, so a *second*
      call with a different `log_dir` silently keeps writing to the first call's file. Real, but
      not reachable through the current codebase's actual usage (`app/main.py` only calls it
      once per process) — left for a future session if a second call site ever gets added.

- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — nothing new to implement
      there, so this session did another focused code-review pass over `backend/`, this time
      targeting parts prior sessions' passes hadn't covered as closely: the previously-untested
      `app/logging/interaction_logger.py` module, `mcp_server_sales/core/server.py`'s top-level
      `handle_message`/`serve()` dispatch loop itself (as opposed to individual tool/prompt/
      resource handlers, which earlier sessions already hardened), and the HTTP transport
      scaffold. Found and fixed three more real, previously-untested bugs, each with a
      regression test verified to fail against the pre-fix code and pass after:
      1. `build_interaction_logger`'s `logging.getLogger(name)` singleton was keyed by `name`
         only, so a second call with a *different* `log_dir` (same default `name`) silently
         kept writing to the first call's file instead of the new one — a real bug flagged (but
         not fixed) by a previous session's review as "not reachable through current usage".
         Fixed by keying the logger by `name` + resolved `log_dir` together. This module had no
         dedicated test file before; added `tests/test_interaction_logger.py`.
      2. `handle_message` called `message.get(...)` unconditionally; a syntactically valid JSON
         document that isn't an object at all (a bare list/string/number — legal JSON, illegal
         JSON-RPC) raised an uncaught `AttributeError` instead of a normal protocol error.
         Separately, `serve()`'s stdio loop called `json.loads(line)` with no guard, so a
         non-JSON line on stdin raised an uncaught `JSONDecodeError`. Either killed the whole
         `mcp-server-sales` subprocess. Fixed both: `handle_message` now returns a JSON-RPC
         `-32600 Invalid Request` for a non-dict message, and `serve()` catches malformed JSON
         and emits a `-32700 Parse error` response before continuing the loop. New test file
         `tests/test_mcp_server_sales_serve.py` exercises `serve()` itself (monkeypatched
         stdin/stdout) — nothing had unit-tested the loop directly before, only `handle_message`.
      3. Same crash class, one level up: `tools/call`, `resources/read`, and `prompts/get` all
         read `params = message.get("params", {})`, which only falls back to `{}` when the key
         is *absent* — a valid request with e.g. `"params": "foo"` (or a list/number) passed a
         non-dict straight into `params.get(...)`, raising an uncaught `AttributeError`. This is
         the same shape of bug an earlier session already fixed one level deeper (explicit
         `"arguments": null`), just not caught at the `params` level itself. Added a shared
         `_params()` helper that normalizes any non-dict `params` to `{}`, used by all three
         methods.
      All three verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end after each fix) and the full suite
      (111 tests, up from 105 at the start of this session, all passing). None needed live
      Ollama - these are pure server/logging-module bugs with no LLM in the loop, so nothing new
      to add to "Needs verification" below.

- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — per this file's own note that a
      future session shouldn't need to re-verify this from scratch every time, did not re-run
      the Docker-daemon check either (already established as an inherent sandbox restriction).
      Instead ran a coverage-guided pass (`coverage run -m pytest` + `coverage report -m`) to
      find genuinely untested code paths, rather than re-reading files a review agent had
      already covered several times. Found and fixed three real things:
      1. `mcp_server_sales/tools/sales_tools.py` (58% covered) and
         `mcp_server_sales/prompts/sales_prompts.py` (81% covered): the success paths of
         `consultar_pedido`, `recomendar_complementos`, `generar_enlace_de_pago`, and the
         `recomendar_outfit` prompt had never been asserted by the test suite — only exercised
         manually via `demo_mcp_sales.py`, or (for `generar_enlace_de_pago`) only through its
         rejection paths. Manually exercised all four to confirm the actual behavior was
         correct, then added 11 new regression tests via `handle_message`/`prompts/get`
         (`tests/test_mcp_server_sales.py`) plus one for `http_server.py`'s previously-untested
         invalid-JSON-body 400 response (`tests/test_mcp_server_sales_http.py`). Both files are
         now at 100% coverage.
      2. Found a real, previously-unfound crash bug while writing the tests above and cross-
         checking `handle_tool_calls` against them: it read `call["function"]["name"]` and
         `call["function"]["arguments"]` unconditionally from each `tool_calls` entry Ollama
         returns. Ollama's normal format always includes both, but — same reasoning this
         project has already applied to malformed MCP server output (a hallucinated tool name,
         an empty `content` list, a non-text content item) — the model is an external system
         this project doesn't control, and a malformed/truncated generation missing either key
         raised an uncaught `KeyError` that killed the whole interactive session before the
         error was even logged. Reproduced the crash manually first, then fixed it: a missing
         `function`/`name` is now caught and reported like the other tool-call failure modes,
         and a missing `arguments` key defaults to `{}` instead of crashing. Two new regression
         tests in `tests/test_handle_tool_calls.py`, confirmed to fail against the pre-fix code
         and pass after (checked by temporarily reverting the fix and re-running).
      3. `README.md`'s terminal-UI section still said "extra credit, in progress", but that
         work (plus its three follow-ups: tool results shown to the user, narrow-terminal
         readability check, demo script styling) was actually completed several sessions ago
         per this file's own Done log. Fixed the README to describe what's actually
         implemented, since documentation accuracy is graded directly.
      All three verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite (124 tests, up
      from 111 at the start of this session, all passing). None needed live Ollama — the new
      crash fix is unit-tested with a fake LLM-shaped `tool_calls` payload, the same pattern
      `tests/test_handle_tool_calls.py` already used for the other failure modes; still worth a
      look during a live run in case a real model ever actually produces a malformed tool call
      (added to "Needs verification" below).

- [x] Re-checked both remaining backlog items again at the start of this session: still
      genuinely blocked on the same things (a live Wireshark capture against a *remote*
      deployment, and no real use case for a binary resource) — nothing new to implement
      there, so this session did another focused code-review/coverage pass over `backend/`
      and found and fixed three more real, previously-untested crash bugs, all the same
      "untrusted external input reaches a lookup/attribute access that assumes a specific
      shape" class earlier sessions already found several instances of, just not these three:
      1. `mcp_server_sales/core/server.py`'s `tools/call` (`name not in DISPATCH`) and
         `mcp_server_sales/prompts/sales_prompts.py`'s `get_prompt`
         (`name not in PROMPT_SPECS_BY_NAME`) both raised an uncaught `TypeError` ("unhashable
         type") on a JSON array/object instead of a string `name`, crashing the whole
         `mcp-server-sales` subprocess — the exact same crash class already fixed for
         `resources/read`'s `uri` in an earlier session, just not extended to these two other
         lookups. Fixed both to catch `TypeError` and treat it as "unknown tool"/"unknown
         prompt" like any other non-match. Two new regression tests
         (`tests/test_mcp_server_sales.py`), confirmed to fail against the pre-fix code.
      2. Same crash class one layer up, client-side: `ToolRegistry.client_for`/
         `client_for_prompt` (`app/mcp_client/registry.py`) only caught `KeyError`, so a
         non-hashable `name` in the LLM's own `tool_calls` payload (a list/dict instead of a
         string — plausible from a malformed/hallucinated generation, the same reasoning
         already applied to a missing `function`/`name`/`arguments` key in an earlier session)
         raised an uncaught `TypeError` that propagated straight through
         `handle_tool_calls`'s `except UnknownToolError` and killed the whole chatbot session.
         Fixed by also catching `TypeError`. Two new regression tests
         (`tests/test_mcp_registry.py`), plus a manual end-to-end check through the real
         `handle_tool_calls` call path confirming the session now reports a normal `[error]`
         line instead of crashing.
      3. `handle_tool_calls` (`app/main.py`) only fell back to `{}` when a tool call's
         `"arguments"` key was *absent* (falsy) — a malformed generation with a non-object
         value there (e.g. a JSON array) passed straight through to
         `render_tool_call(name, arguments)`, whose `arguments.items()` raised an uncaught
         `AttributeError` before the tool was even called, crashing the session. Normalized any
         non-dict `arguments` value to `{}`. New regression test in
         `tests/test_handle_tool_calls.py`, confirmed to fail against the pre-fix code with the
         exact predicted `AttributeError`.
      All three verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite (129 tests, up
      from 126 at the start of this session, all passing). None needed live Ollama — all three
      are pure lookup/attribute-access bugs reachable with a hand-built malformed payload, the
      same pattern every prior crash fix in this project's history has used; nothing new to add
      to "Needs verification" below beyond what's already there about malformed-tool-call
      handling in general.
      Ran a coverage report (`coverage run -m pytest` + `coverage report -m`) before concluding
      this pass: overall coverage is 94%, and the remaining gaps are exactly the same kind
      already noted as fine in earlier sessions — real subprocess-launching wiring
      (`connect_sales_mcp_server`/`connect_filesystem_mcp_server`/`connect_git_mcp_server`),
      `app/main.py`'s `run()`/`__main__` entrypoint, and `mcp_server_sales/core/http_server.py`'s
      `serve_http()` — all integration glue that's exercised for real via
      `python -m app.demo_mcp_sales` and the real-subprocess test files rather than mocked unit
      tests, not undiscovered bug surface.

- [x] First real local verification session on the student's own Windows machine (everything
      before this was sandbox-only, per the "Needs verification" notes below). Set up the local
      environment: installed `uv` (winget, needed for `uvx`/the git MCP server), installed
      `backend/requirements.txt` into the existing `.venv` (`rich` was missing), confirmed
      Ollama was already installed with `qwen2.5:7b` pulled, confirmed git identity was already
      configured globally. Found and fixed two real bugs surfaced only by testing on Windows for
      the first time:
      1. `StdioTransport.__init__` (`app/mcp_client/transports/stdio.py`) called
         `subprocess.Popen(["npx", ...])` / `Popen(["uvx", ...])` directly, which crashed with
         `FileNotFoundError` on Windows: `npx` resolves to an `npx.cmd` shim there, and
         `CreateProcess` can't exec a `.cmd` file directly the way it execs a real binary on
         POSIX. This is exactly the platform the assignment will be run and presented on, so it
         was a real, would-have-failed-the-demo bug, not a hypothetical one. Fixed by resolving
         the command through `shutil.which()` before `Popen` (PATHEXT-aware on Windows, a
         harmless no-op lookup on POSIX where `npx`/`uvx`/`python` already resolve directly).
         Two new regression tests in `tests/test_stdio_transport.py`.
      2. The filesystem+git demo scenario from the assignment (section 4, functionality #4: "ask
         the chatbot to create a repo, create a README, add it, and commit it") was flaky against
         the real local model (`qwen2.5:7b`): the filesystem tool is scoped to the workspace root
         while the git tools operate on the `demo-repo` subfolder, and the old `SYSTEM_PROMPT`
         only described that relationship in prose. The model wrote the README at the workspace
         root (outside the repo) once, and separately tried relative/half-remembered absolute
         `repo_path` values for `git_add`/`git_commit` that didn't resolve to the real repo,
         burning tool-call rounds and hitting `MAX_TOOL_ROUNDS` without ever committing (or, in
         one run, letting the official git server produce a misleadingly "successful" empty
         commit while the bot told the user it had committed the file). Reworded `SYSTEM_PROMPT`
         in `app/main.py` to spell out the exact literal `repo_path` string to copy verbatim for
         every git tool call, to write repo-bound files at `demo-repo/<filename>`, and to only
         report success to the user when the tool result actually confirms it. Verified for real,
         repeatedly, against the live chatbot (`python -m app.main`, real Ollama, real
         filesystem/git subprocesses): the scenario now reliably completes in 3 tool-call rounds
         (`write_file` -> `git_add` -> `git_commit`) with a real commit landing in the repo (confirmed
         via `git log --stat`). No test asserts on the prompt's exact wording (nothing did
         before either), so no test changes needed here beyond the transport fix above.
      Also did a full live pass through the "Needs verification" list below with a real Ollama
      server and all three real MCP server subprocesses (sales/filesystem/git) - see that section
      for what's now confirmed vs. still open. Full suite: 133 passed (up from 131), all on this
      machine, not the cloud sandbox.

- [x] Wireshark capture against the live remote deployment, done interactively on the
      student's own Windows machine (this session), with the student's go-ahead. Set
      `SALES_MCP_URL` to the Cloud Run URL and `SSLKEYLOGFILE` to a local file (natively
      supported by `requests`/urllib3 - no code change needed), captured with `tshark`
      filtered to the Cloud Run service's resolved IPs while driving two real user turns
      through `python -m app.main` (a product search, an order lookup), then decrypted the
      capture in Wireshark/`tshark` using that keylog. Captured and classified all 6
      JSON-RPC exchanges: `initialize` + `notifications/initialized` (sync), `tools/list`,
      `prompts/list`, and two `tools/call`s (request/response). Confirmed each connection
      does a full TCP three-way handshake + TLS 1.2 ClientHello/TLS 1.3 ServerHello per
      JSON-RPC call (no `requests.Session` reuse in `HttpTransport`, noted as a real but
      out-of-scope-for-now efficiency observation, not a bug - functionally correct).
      Artifacts saved at `docs/wireshark/mcp_remote_capture.pcapng` and
      `docs/wireshark/tls_keylog.log`. No code changed for this item; it was pure capture
      and analysis.
- [x] Report section 9 (link/network/transport/application-layer analysis of the Wireshark
      capture above, with the real decrypted JSON-RPC frames and a request/response table)
      and section 10 (conclusions) written in `docs/report/informe.md`. Also fixed a stale
      line in section 8.1 that still said the HTTP transport was "sin desplegar" even
      though the remote deployment had already happened in an earlier session.
- [x] Web frontend, done with the student present in this session, at the student's request
      (to demo as a Web app in the presentation instead of the terminal — the assignment's
      15% UI extra credit only counts once regardless of terminal-vs-Web and is already
      earned via the `rich` terminal UI, so this was purely for the demo, not for extra
      points). Filled in the previously-empty `frontend/` scaffold from the original
      "Arquitectura" commit and added a new `backend/app/web/` package:
      - `app/web/api.py`: a small FastAPI app exposing `POST /api/chat` and `GET /api/servers`,
        and serving `frontend/public/index.html` (plain HTML/CSS/JS, no build step) on the same
        origin, so no CORS setup was needed. Deliberately reuses `app.main.run_turn` (and the
        `connect_*_mcp_server`/`parse_prompt_command`/`prompt_text` helpers) as-is instead of
        re-implementing the tool-calling loop for the web path — the only genuinely new logic
        is `events_since()`, which reconstructs a JSON event list (tool calls/results) from
        the session messages a turn appended, by reading back what `add_assistant_message`/
        `add_tool_result` already store, rather than duplicating `handle_tool_calls`. This
        keeps the web surface from being able to drift from the already-tested CLI behavior.
      - App-factory pattern (`create_app(llm_client=None, registry=None, ...)`): production
        (`python -m app.web`) calls it with no arguments, so its `lifespan` connects the three
        real MCP servers and a real `OllamaClient` on startup exactly like `app.main.run()`
        does; tests pass fakes directly, which skips real connections entirely. 6 new tests
        (`tests/test_web_api.py`), using the same `FakeLLM`/`FakeClient` pattern
        `tests/test_run_turn.py` already established.
      - `frontend/public/index.html`: single-page chat client, no framework/build step. Same
        color convention as `app/ui/console.py` (cyan = user, green = bot reply panel, dim
        yellow = background tool-call activity, red = errors) for visual consistency between
        the two UIs.
      - Verified for real, not just via the mocked tests: ran `python -m app.web` against the
        student's actual machine — all three real MCP server subprocesses connected
        (confirmed via `GET /api/servers`), the static page served correctly, a plain question
        got a real Ollama reply, a follow-up question resolved context correctly ("¿Quién fue
        Alan Turing?" → "¿En qué fecha nació?"), and a product question triggered a real
        `buscar_productos` tool call against the sales server with the `tool_call`/
        `tool_result` events coming through in the API response exactly as the frontend
        expects. Also verified the graceful-failure path for real: hit `/api/chat` while
        Ollama was still starting up and got a clean `{"reply": "", "events": [{"type":
        "error", ...}]}` instead of a crash. Full suite: 139 passed (up from 133).
      - Removed `frontend/public/.gitkeep`, now redundant since the folder has real content.
        `frontend/src/components/`, `frontend/src/lib/`, `mcp-servers-config/`, and
        `network-analysis/captures/` are still empty scaffolding from the same original
        "Arquitectura" commit and were deliberately left alone — the student was asked and
        hadn't confirmed removing those when this session ended.

- [x] Re-checked the one remaining backlog item at the start of this session (the binary
      resource, below): still no genuine use case, nothing new to implement there. The web
      frontend added last session was also new ground no review pass had looked at closely yet,
      so this session did a focused code-review pass centered on the web API and the client-side
      JSON-RPC parsing it (and the CLI) both depend on. Found and fixed three more real,
      previously-untested crash bugs, each with a regression test confirmed to fail against the
      pre-fix code and pass after:
      1. `prompt_text()` (`app/main.py`) indexes `message["content"]["text"]` unconditionally on
         a `prompts/get` result. Both call sites — `app/main.py`'s CLI `/prompt` handler and the
         new `app/web/api.py`'s `/api/chat` handler — called it *outside* the `try/except`
         wrapping `client_for_prompt`/`get_prompt`, so a malformed result (e.g. a message missing
         `"content"`) raised an uncaught `KeyError` and crashed the session/request instead of
         the normal error response every other prompt failure already got. Fixed by moving the
         `prompt_text()` call inside each `try` block. New regression test in
         `tests/test_web_api.py` (the CLI path mirrors the same fix but has no unit-test harness
         for `run()`, same as other `run()`-only fixes in this project's history).
      2. `parse_response()` (`app/mcp_client/protocol.py`) called `error.get(...)` unconditionally
         on a JSON-RPC response's `"error"` field. The spec requires that field to be an object,
         but a peer this project doesn't control (the official filesystem/git servers, or a
         future remote deployment reached over the network) could send something else — a bare
         string, say — raising an uncaught `AttributeError` that bypassed every caller's
         `except (MCPProtocolError, ConnectionError)` net. Now raises a normal
         `MCPProtocolError` instead when `error` isn't a dict. New regression test in
         `tests/test_mcp_client.py`.
      3. `MCPClient._call()` (`app/mcp_client/client.py`) did `"id" not in response`
         unconditionally after `transport.receive()`. Both transports only guarantee valid JSON,
         not a JSON-RPC *object* — a bare number crashed with an uncaught `TypeError`, and (found
         while writing the regression test) a bare string/list would have silently looped
         forever instead, since substring/element membership never happens to match `"id"`,
         hanging the whole session waiting for a "matching" message that would never come. Now
         raises `MCPProtocolError` on a non-dict response. New regression test in
         `tests/test_mcp_client.py`.
      All three verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end after each fix) and the full suite
      (142 passed, up from 139 at the start of this session). None needed live Ollama — all
      three are pure malformed-external-response bugs reachable with a hand-built payload, the
      same pattern nearly every prior crash fix in this project's history has used.

- [x] Re-checked the one remaining backlog item at the start of this session (the binary
      resource, below): still no genuine use case, nothing new to implement there. Also fixed
      the stale local `main` branch pointer left over from the previous session ended while
      `HEAD` was detached (`origin/main` already had everything, just fast-forwarded local
      `main` to match, same situation this file already has a note about below). This session
      did another focused code-review pass over `backend/`, targeting call sites that read
      external/third-party data with an assumed shape that prior sessions' passes hadn't
      checked as closely. Found and fixed three more real, previously-untested crash bugs, each
      with a regression test confirmed to fail against the pre-fix code and pass after:
      1. `ToolRegistry.register()` (`app/mcp_client/registry.py`) indexed `spec["name"]`
         unconditionally for both tools and prompts. A connected server - including the
         official filesystem/git servers, which are third-party code this project doesn't
         control, or a future remote deployment - is only guaranteed to return valid JSON, not
         a well-formed tool/prompt spec; a spec missing `"name"` (or with a non-string one)
         raised an uncaught `KeyError` at startup, before the chat loop even began, killing the
         whole session before it could do anything. Added a `_spec_name()` helper that returns
         `None` for a malformed spec, so `register()` now just skips it (a nameless tool can't
         be routed or called anyway) instead of crashing. Verified for real against the actual
         official filesystem MCP server subprocess (still registers all 14 of its real tools
         correctly after the fix). 3 new regression tests (`tests/test_mcp_registry.py`).
      2. `OllamaClient.chat_raw` (`app/llm/ollama_client.py`) checked `"message" not in data`
         unconditionally after parsing the response body as JSON. A 200 response can be valid
         JSON without being a JSON *object* - e.g. a bare `null` - and `in` on a non-iterable
         scalar (`None`, a number, a bool) raises `TypeError` instead of failing the membership
         check, so this used to crash straight out of `chat_raw` instead of raising the
         documented `OllamaConnectionError` that `run_turn` relies on to keep the session alive
         after a bad LLM response. Fixed by checking `isinstance(data, dict)` first. Mocked per
         the project's testing convention (no live Ollama in this sandbox) - 1 new regression
         test in `tests/test_ollama_client.py`.
      3. `extract_tool_result_text()` (`app/main.py`), called from `handle_tool_calls` right
         after a successful `call_tool`, indexed `result.get("content")` unconditionally. A
         JSON-RPC response's `"result"` is only guaranteed present when there's no `"error"` -
         it can legally be `null` or any other JSON value, not the `{content, isError}` shape a
         well-formed `tools/call` result has, and that call site sits *outside* the
         `try/except` that already handles a failed tool call, so a connected server sending a
         null/malformed result raised an uncaught `AttributeError` and crashed the whole
         session instead of reporting a normal (if uninformative) tool result. Fixed the same
         way as the MCP client's own non-dict-response hardening from an earlier session:
         treat a non-dict `result` as having no content. 2 new regression tests
         (`tests/test_handle_tool_calls.py`), one at the unit level and one exercised through
         the real `handle_tool_calls` call path.
      All three verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end after each fix) and the full suite
      (148 passed, up from 142 at the start of this session). None needed live Ollama - all
      three are pure malformed-external-response bugs reachable with a hand-built payload, the
      same pattern nearly every prior crash fix in this project's history has used; nothing new
      to add to "Needs verification" below beyond what's already there.

- [x] Re-checked the one remaining backlog item at the start of this session (the binary
      resource, below): still no genuine use case, nothing new to implement there. Also
      corrected a stale claim in this file: the "Explicitly OUT of scope" section said
      presentation prep was "still open" with only "an outline/talking points doc" possible
      ahead of time, but that outline already exists and is thorough
      (`docs/presentacion.md`, written in an earlier student-present session alongside the
      web frontend work) - a full rubric-mapped script with a pre-demo checklist, a live
      demo script per rubric section, anticipated difficulties/lessons-learned narration,
      and expected Q&A. Nothing left to draft there; only the live demo itself still needs
      the student (see the corrected note below).
      Before another code-review pass, did an honest check of whether one was still likely
      to find anything: read through every file this session's review passes (spanning many
      prior sessions, see Done log above) hadn't specifically covered yet or had covered only
      lightly - `mcp_server_sales/prompts/sales_prompts.py`, `resources/catalog_resource.py`,
      `resources/policies.py`, `tools/sales_tools.py`'s actual business logic (not just its
      crash-safety net), `app/mcp_client/adapters.py`, `app/mcp_client/protocol.py`,
      `app/mcp_client/transports/http.py`, `mcp_server_sales/core/http_server.py`, and
      `frontend/public/index.html`'s JS - and traced each remaining coverage gap reported by
      `coverage report -m` back to its call site. Unlike every prior review-pass session,
      this one came up clean: every previously-flagged-as-risky shape (non-hashable
      lookups, non-dict arguments/params, non-string names) is already guarded at the
      exact call sites checked, and the remaining uncovered lines are genuinely just
      integration glue (real subprocess/network wiring exercised via
      `python -m app.demo_mcp_sales` and the real-subprocess test files, not unit-mocked)
      - the same category already noted as fine in earlier sessions' coverage passes. Worth
      recording plainly: this is the first session where a dedicated bug-hunt pass found
      zero new crash bugs, after eight consecutive sessions that each found two-to-five real
      ones - a genuine (not assumed) signal that this class of defensive-coding work is
      largely exhausted for the current feature set, not a reason to stop checking if the
      feature set grows.
      Redirected the session's effort to two real, previously-untested coverage gaps found
      during that same pass instead of forcing another bug-hunt narrative:
      1. `StdioTransport.send()` (`app/mcp_client/transports/stdio.py`) had zero direct unit
         test coverage - only ever exercised indirectly through real subprocess integration
         tests. Added a unit test asserting the actual wire contract the stdio MCP transport
         spec requires (one newline-delimited JSON line, no embedded newlines, immediate
         flush) - real behavior this project depends on but had never asserted directly.
      2. `mcp_server_sales/__main__.py`'s `parse_args()` had zero test coverage, despite being
         the literal Cloud Run container entrypoint (unmodified) documented in
         `docs/spec/mcp_server_sales.md`'s "Remote deployment" section - the HOST/PORT
         env-var defaults it reads are exactly what Cloud Run injects. Added 5 tests: the
         stdio default, the HTTP-transport env-var defaults, explicit CLI flags overriding
         those env vars, and argparse rejecting an unknown `--transport` value.
      Both verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and manually via `curl` against
      `python -m mcp_server_sales --transport http` (still serves correctly), plus the full
      suite (154 passed, up from 148 at the start of this session). Neither needed live
      Ollama - both are pure argument-parsing/framing tests with no LLM in the loop.

- [x] Re-checked the one remaining backlog item at the start of this session (the binary
      resource, below): still no genuine use case (no images/binary documents in
      `backend/mcp_server_sales/data/catalog.py`), nothing new to implement there. Also fixed
      a stale local `main` branch pointer left over from the previous session, same recurring
      situation this file already had two notes about (`origin/main` was already correct; a
      detached-`HEAD` session just hadn't fast-forwarded local `main` before ending) - confirmed
      via `git merge-base --is-ancestor origin/main HEAD` before fast-forwarding, pushed, no
      commits lost. Then did another focused code-review pass over `backend/`, specifically
      re-reading `app/mcp_client/client.py` (the hand-rolled MCP client core) end to end rather
      than only the files earlier sessions' passes had flagged as risky. Found and fixed one
      more real, previously-untested crash bug, the same "untrusted external response reaches a
      lookup that assumes a specific shape" class nearly every prior session's fix in this
      project's history has used, just one more instance of it:
      1. `MCPClient.list_tools`/`list_resources`/`read_resource`/`list_prompts`
         (`app/mcp_client/client.py`) all returned `(result or {}).get(<key>, [])`. `or` only
         falls back to `{}` when `result` is *falsy* (`None`, `{}`) - a connected server
         (including the official filesystem/git servers, third-party code this project doesn't
         control, or a future remote deployment reached over the network) sending a truthy
         non-dict `"result"` (e.g. a bare string or a list - legal JSON-RPC, since the spec
         doesn't constrain `result`'s shape) reached `.get(...)` on that str/list and raised an
         uncaught `AttributeError`. Reproduced the crash manually first (`result: "oops"` on a
         `tools/list` response) before fixing it, same as every prior session's crash-fix
         methodology here. Fixed all four methods to check `isinstance(result, dict)` explicitly
         instead of relying on truthiness. 4 new regression tests
         (`tests/test_mcp_client.py`), each confirmed to fail against the pre-fix code (verified
         by temporarily stashing the fix and re-running) and pass after. This matters most for
         `ToolRegistry.register()`, called at startup for every connected server - an
         unguarded crash there would have killed the whole chatbot session before the chat loop
         even began, the same severity class as the malformed-tool-spec bug fixed in an earlier
         session.
      Also added 2 more regression tests (`tests/test_mcp_registry.py`) closing a real coverage
      gap found while re-reading `registry.py` alongside the fix above: `_spec_name()`'s
      `isinstance(spec, dict)` guard (for a tools/prompts list entry that isn't even a dict -
      e.g. a bare string) had correct behavior already but zero direct test coverage before -
      every existing test only covered a dict-shaped-but-incomplete spec (missing/non-string
      `"name"`), not a non-dict entry in the list at all. `registry.py` is now at 100% line
      coverage (was 98%).
      Went on to re-read every other module this session hadn't already covered
      (`app/chat/session.py`, `app/logging/interaction_logger.py`,
      `mcp_server_sales/tools/sales_tools.py`, `mcp_server_sales/resources/*.py`,
      `mcp_server_sales/prompts/sales_prompts.py`, `mcp_server_sales/core/server.py`,
      `app/main.py`'s connector functions and `run()`, `app/ui/console.py`,
      `app/web/api.py`, and `frontend/public/index.html`'s JS) looking for the same bug
      class (external/malformed data reaching an unguarded lookup or attribute access) one
      more time - unlike the fix above, this came back clean: every other call site handling
      external server/LLM/frontend-event data is already guarded the same way (an
      `isinstance` check, a `.get()` with an explicit dict default, or a `try/except` net),
      matching what an earlier session's own coverage-guided pass already concluded about the
      rest of the tree.
      Both changes verified against the real `mcp_server_sales` subprocess via `python -m
      app.demo_mcp_sales` (still runs correctly end-to-end) and the full suite (160 passed, up
      from 154 at the start of this session). Neither needed live Ollama - both are pure
      malformed-external-response bugs/coverage gaps reachable with a hand-built payload, the
      same pattern nearly every prior crash fix in this project's history has used; nothing new
      to add to "Needs verification" below beyond what's already there.

### Backlog (work in this order, roughly 3 real+tested commits per session)
- [ ] Consider adding more MCP resource shapes beyond text/JSON (e.g. a `blob`/binary resource)
      only if a real use case for one shows up in the sales server's scope — no forced work here
      just to demonstrate the shape. Re-checked this session again: the current catalog/order
      data (`backend/mcp_server_sales/data/catalog.py`) has no images or binary documents, so
      there's still no genuine fit — nothing implemented, left for a future session if the scope
      grows (e.g. product photos).

The binary-resource item has been re-checked and found still-blocked (no genuine use case)
across several consecutive sessions with no change — no need to re-verify from scratch every
time; only re-check if the catalog scope actually grows (e.g. product photos get added). Both
of the blockers that used to sit alongside it (remote deployment, then the Wireshark capture)
are now resolved (see Done log) — presentation prep is the only thing explicitly left, and
that needs the student directly (see "Explicitly OUT of scope" below).

### Needs verification by the student on their own machine
**Update from the first real local-machine session (this one):** confirmed live and working on
the student's own Windows machine, real Ollama (`qwen2.5:7b`), real subprocesses for all three
MCP servers: a plain conversational turn, context carried across turns, tool-calling for
`buscar_productos` (chained correctly from a natural-language question), the full
filesystem+git demo scenario (write README -> git add -> git commit, real commit confirmed via
`git log`, after the `SYSTEM_PROMPT` fix noted above), `/prompt resumen_pedido pedido_id=...`,
and the terminal UI's colored panels/tool-call lines rendering correctly in a real Windows
terminal. The bullets below predate this session and are kept for what's still genuinely
unconfirmed (a real MCP server dying mid-session, the malformed-tool-call-from-the-model path,
narrow-terminal contrast in the student's actual color theme, the exact 200-char truncation
feel).
- New this session: the `handle_tool_calls` fix for a `tool_calls` entry missing
  `function`/`name`/`arguments` is unit-tested with a fake payload shaped like Ollama's format,
  but wasn't (and, by nature, can't reliably be) triggered by a real model during a live run —
  it depends on the model actually producing a malformed tool call. Not something to go chasing
  on purpose, just worth knowing about: if a live session ever prints `[error] Malformed tool
  call from the model: ...` instead of crashing outright, that's this fix working as intended.
- New this session: the `parse_prompt_command` fix (rejecting ordinary chat text that merely
  starts with "/prompt") is unit-tested, but wasn't exercised through the actual interactive
  `python -m app.main` loop for the same sandbox reason as the rest of this list. Worth typing a
  real message starting with "/prompt" (that isn't meant as a command) during a live run to
  confirm it now reaches the LLM normally instead of being swallowed.
- New this session: the two crash fixes above (`handle_tool_calls`'s `extract_tool_result_text`,
  `OllamaClient.chat_raw`'s response-parsing guard) are unit-tested and the sales server was
  re-verified via `python -m app.demo_mcp_sales`, but neither was exercised through a live
  `python -m app.main` session with a real Ollama model, for the same sandbox reason as the rest
  of this list. The `OllamaClient` one is worth a real look: if you ever see the chatbot print an
  `[error]` line mentioning "unexpected response shape" during a live run, that means Ollama
  returned something other than a normal chat message (e.g. an error payload) and would be a
  real sign worth investigating, not a false positive.
- New this session: the four bug fixes above (`buscar_productos` crash, `generar_enlace_de_pago`
  validation, `StdioTransport` hardening, the startup subprocess-leak fix in `app/main.py`) are
  all unit-tested and the sales server was re-verified against its real subprocess via
  `python -m app.demo_mcp_sales`, but none were exercised through a live `python -m app.main`
  session with a real Ollama model driving tool calls, for the same sandbox reason noted below.
  Worth a quick look during your next live run, especially the `StdioTransport.close()` fix (kill
  on a slow-exiting subprocess) since that only really shows up under real process timing.
- Checked this session whether Docker could be used to prepare (and locally test) a container for
  the section-6 remote deployment ahead of time: the `docker` CLI is present in this sandbox but
  its daemon cannot be started here (`ulimit: error setting limit (Operation not permitted)` from
  `service docker start`), so no Dockerfile was written — an untested Dockerfile wouldn't meet
  this project's "real, tested" bar, and per the working agreement this is exactly the kind of
  step that needs the student's own machine/cloud account rather than a workaround. Still
  genuinely blocked; no need to re-attempt this in sandbox in a future session.
- New this session: the terminal UI (`app/ui/console.py`, `rich` dependency) was verified to
  emit correct ANSI color codes under a real pseudo-tty in this sandbox (`script -qc ...`) at
  both a normal (100-column) and a narrow (40-column) width, and the rendering logic itself is
  unit-tested, but its actual on-screen readability (whether the chosen colors have enough
  contrast in your terminal's actual color theme/light-vs-dark background) was not checked
  against a real interactive session. Run `python -m app.main` in your own terminal and confirm
  the banner, bot-reply panels, tool-call/tool-result lines and errors all look right.
- New this session: tool call results are now printed to the terminal (`render_tool_result`),
  not just fed back to the LLM. Verified for real under a pseudo-tty that the dim-yellow ANSI
  codes come out correctly, but not seen yet inside an actual live `python -m app.main` session
  with a real Ollama model driving the tool calls - worth a look while you're doing the live run
  below, to confirm the 200-char truncation doesn't feel too aggressive or too loose for the
  kinds of results your tools actually return.
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
- The `/prompt <name> key=value ...` chatbot command (now routed through
  `ToolRegistry.client_for_prompt`, generalized this session) was verified for real against the
  `mcp-server-sales` subprocess directly (`prompts/list`/`prompts/get` over real stdio) and the
  registration path was verified against the real official filesystem server subprocess, but not
  through the actual interactive `python -m app.main` loop with a live Ollama model, for the same
  sandbox reason as above. Please try `/prompt resumen_pedido pedido_id=PED-1001` and
  `/prompt recomendar_outfit ocasion=boda presupuesto=500` once locally and confirm the model
  picks up the injected prompt text and calls the right tools in response.
- This session's `handle_tool_calls` error-handling fix (catching `MCPProtocolError`/
  `ConnectionError` around a tool call) is unit-tested with a fake client, but wasn't exercised
  through a live run where a real MCP server subprocess actually dies mid-session. If you want to
  see it for real, start `python -m app.main` and kill one of the MCP server subprocesses (e.g.
  `pkill -f mcp_server_sales`) mid-conversation, then ask something that needs that server's
  tool — the chatbot should print an `[error]` line and keep running instead of crashing.

### Note: stale local `main` branch pointer at the start of this session
This session started with `HEAD` detached at the tip of the previous session's work
(`e703143`) while the local `main` branch ref was still pointing at an older commit
(`cdafed7`) — `origin/main` itself was already correctly at `e703143`, so nothing was lost,
but a local `git log`/`git branch` in that state looked alarming (20 "unpushed" commits that
were, in fact, already on GitHub). Fixed by resetting local `main` to `origin/main` before
starting new work. If a future session sees a detached `HEAD` again, fetch `origin/main` and
compare commit hashes before assuming anything needs re-pushing.

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
- Wireshark capture and analysis: done (see Done log above) — it needed the student's own
  local network/machine and was run interactively with the student present in this
  session, not by an autonomous cloud-sandbox agent.
- Presentation prep: the outline/talking-points doc is done (`docs/presentacion.md` —
  pre-demo checklist, rubric-mapped feature walkthrough, difficulties/lessons-learned
  narration, anticipated Q&A). Giving the actual live presentation still needs the student.

## Working agreement for autonomous sessions
- Aim for ~3 atomic, real, tested commits per run. No filler or empty commits just to
  raise the count — every commit must be working, reviewed-by-yourself code.
- Update this file's Status section at the end of every run: move finished items to
  Done, and note anything you had to stop on.
- If a step needs credentials, secrets, or local hardware you don't have in the cloud
  sandbox, stop and note it here instead of improvising around it.
- Push to `main` when done; there is no PR review step, so keep each commit safe to
  ship on its own.
