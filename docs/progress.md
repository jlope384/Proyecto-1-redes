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

### Backlog (work in this order, roughly 3 real+tested commits per session)
- [ ] Report section 9 (link/network/transport-layer analysis from a Wireshark capture) and
      section 10 (conclusions) — cannot be written yet: section 9 needs a real Wireshark
      capture against the *remote* deployment (student's own machine/network), and conclusions
      are premature before the remote deployment and presentation are done. Revisit once the
      remote deployment (see below) exists.
- [ ] Consider adding more MCP resource shapes beyond text/JSON (e.g. a `blob`/binary resource)
      only if a real use case for one shows up in the sales server's scope — no forced work here
      just to demonstrate the shape. Re-checked this session again: the current catalog/order
      data (`backend/mcp_server_sales/data/catalog.py`) has no images or binary documents, so
      there's still no genuine fit — nothing implemented, left for a future session if the scope
      grows (e.g. product photos).

Both items above have now been re-checked and found still-blocked across several consecutive
sessions with no change in their blockers — a future session shouldn't need to re-verify this
from scratch every time; only re-check if something about the environment actually changes
(e.g. the remote deployment gets done, or product images get added to the catalog).

### Needs verification by the student on their own machine
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
