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

More features (official Filesystem/Git MCP servers, remote deployment, Wireshark analysis) will be
added incrementally as the project progresses — see `docs/progress.md` for the live backlog.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running locally, with a model pulled, e.g.:

  ```
  ollama pull qwen2.5:7b
  ```

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # on Windows
pip install -r requirements.txt
```

By default the client uses model `qwen2.5:7b` against `http://localhost:11434`. Override with
environment variables if needed:

```bash
set OLLAMA_MODEL=llama3
set OLLAMA_HOST=http://localhost:11434
```

## Usage

```bash
cd backend
python -m app.main
```

Type your messages at the `You:` prompt; type `exit` to quit. Try asking about products, e.g.
"Tienen camisas azules y cuanto cuestan?" — the model will call the sales MCP server for real data.

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
