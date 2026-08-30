# Proyecto 1 - MCP Chatbot (CC3067 Redes)

A terminal chatbot host that talks to a local LLM through [Ollama](https://ollama.com/) and, going
forward, to tools exposed by Model Context Protocol (MCP) servers over JSON-RPC.

## Features implemented so far

- **LLM connection over its API**: `backend/app/llm/ollama_client.py` calls the local Ollama
  `/api/chat` endpoint directly over HTTP (no MCP/LLM SDKs).
- **Conversation context**: `backend/app/chat/session.py` keeps the full message history for a
  session so follow-up questions ("when was he born?") resolve correctly.
- **Interaction logging**: `backend/app/logging/interaction_logger.py` writes every request/response
  exchanged with the LLM and MCP servers to `backend/logs/interactions.log` as JSON lines.
- **MCP client, implemented by hand**: `backend/app/mcp_client/` speaks JSON-RPC 2.0 directly
  (no MCP SDK) over a stdio subprocess transport — `initialize` handshake, `tools/list`,
  `tools/call`, `resources/list`, `resources/read`.
- **Sales MCP server (local, industry use case)**: `backend/mcp_server_sales/` is a hand-rolled
  JSON-RPC server exposing `buscar_productos`, `consultar_inventario`, `consultar_pedido`,
  `recomendar_complementos` and `generar_enlace_de_pago` as tools, plus shipping/warranty/returns
  policies as resources. See `docs/annotated-Propuesta mcp.pdf` for the use-case writeup.
- **Chatbot uses the MCP server via the LLM's tool-calling**: `backend/app/main.py` gives Ollama
  the sales server's tools; when the model decides to call one, the chatbot executes it through the
  real MCP client and feeds the result back for a grounded answer.
- **Official Filesystem MCP server**: `backend/app/main.py` also launches the official
  `@modelcontextprotocol/server-filesystem` (via `npx`) scoped to `backend/workspace/`, and merges
  its tools with the sales server's through `app/mcp_client/registry.py`, which routes each tool
  call to the server that owns it. Ask the bot to save or read a note and it will use it.
- **Official Git MCP server**: `backend/app/main.py` also launches `mcp-server-git` (via `uvx`)
  against a demo repository at `backend/workspace/demo-repo/` (created automatically on first
  run, since that server has no `git_init` tool). Ask the bot to write a README and commit it, and
  it will use the filesystem tools to write the file and the git tools (`git_add`, `git_commit`,
  `git_log`, ...) to commit it for real. This requires a git identity configured globally
  (`git config --global user.name/user.email`), or `git_commit` will fail.
- **MCP prompts**: the sales server exposes reusable prompt templates (`recomendar_outfit`,
  `resumen_pedido`) via `prompts/list`/`prompts/get`. Type `/prompt <name> key=value ...` at the
  chatbot's `You:` prompt to start a turn from one of them instead of free-typed input.
- **Chained tool calls in one turn**: the chatbot can call more than one tool per user turn (e.g.
  search a product, then check its stock) - it keeps offering tools back to the LLM across up to
  five rounds instead of stopping after the first tool call.

- **HTTP transport scaffold for the sales server**: `mcp_server_sales/core/http_server.py` exposes
  the same hand-rolled `handle_message` JSON-RPC logic over a single `POST /rpc` HTTP endpoint
  (stdlib `http.server`, no MCP SDK), so the server can eventually run as a standalone process
  instead of only as a subprocess launched over stdio. Run it with
  `python -m mcp_server_sales --transport http --port 8765`. `app/mcp_client/transports/http.py`
  is the matching client-side transport (same `send`/`receive`/`close` interface as the stdio
  transport). This is a scaffold, not a deployment: actual cloud hosting is out of scope for now
  (see `docs/progress.md`), and the chatbot in `app/main.py` still uses stdio for all three
  servers.

- **Terminal UI (extra credit, in progress)**: `backend/app/ui/console.py` renders the chatbot
  through [`rich`](https://github.com/Textualize/rich) instead of plain `print()`: the user prompt,
  bot replies (boxed in their own panel), background MCP tool-call activity, errors and the startup
  banner each get a fixed color chosen for visual hierarchy, following standard color-psychology
  conventions (cyan = user input, green = the bot's actual answer, dim yellow = secondary/
  in-progress tool activity, red = errors, blue = system info). Tool calls are now also visibly
  announced before they run, which previously happened silently.

More features (remote deployment, Wireshark analysis) will be added incrementally as the project
progresses — see `docs/progress.md` for the live backlog.

## Requirements

- Python 3.10+
- Node.js + `npx` (used to run the official Filesystem MCP server)
- [uv](https://docs.astral.sh/uv/) (`uvx`, used to run the official Git MCP server)
- [Ollama](https://ollama.com/) installed and running locally, with a model pulled, e.g.:

  ```
  ollama pull qwen2.5:7b
  ```

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # on Linux/macOS
.venv\Scripts\activate       # on Windows
pip install -r requirements.txt
```

By default the client uses model `qwen2.5:7b` against `http://localhost:11434`. Override with
environment variables if needed:

```bash
export OLLAMA_MODEL=llama3        # on Linux/macOS
export OLLAMA_HOST=http://localhost:11434

set OLLAMA_MODEL=llama3           # on Windows (cmd)
set OLLAMA_HOST=http://localhost:11434
```

## Usage

```bash
cd backend
python -m app.main
```

Type your messages at the `You:` prompt; type `exit` to quit. Try asking about products, e.g.
"Tienen camisas azules y cuanto cuestan?" — the model will call the sales MCP server for real data.

To start a turn from one of the sales server's prompt templates instead of free-typed input:

```
You: /prompt resumen_pedido pedido_id=PED-1001
You: /prompt recomendar_outfit ocasion=boda presupuesto=500
```

To review everything logged during a session (every LLM and MCP request/response, from
`backend/logs/interactions.log`):

```bash
cd backend
python -m app.main --show-log
```

To see the raw MCP protocol exchange (initialize, tools/list, tools/call, resources/read) without
the LLM in the loop:

```bash
cd backend
python -m app.demo_mcp_sales
```

## Tests

```bash
cd backend
python -m pytest
```
