# Proyecto 1 - MCP Chatbot (CC3067 Redes)

A terminal chatbot host that talks to a local LLM through [Ollama](https://ollama.com/) and, going
forward, to tools exposed by Model Context Protocol (MCP) servers over JSON-RPC.

## Features implemented so far

- **LLM connection over its API**: `backend/app/llm/ollama_client.py` calls the local Ollama
  `/api/chat` endpoint directly over HTTP (no MCP/LLM SDKs).
- **Conversation context**: `backend/app/chat/session.py` keeps the full message history for a
  session so follow-up questions ("when was he born?") resolve correctly.
- **Interaction logging**: `backend/app/logging/interaction_logger.py` writes every request/response
  exchanged with the LLM (and later, MCP servers) to `backend/logs/interactions.log` as JSON lines.

More features (MCP client, local/remote MCP servers, Wireshark analysis) will be added
incrementally as the project progresses.

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

Type your messages at the `You:` prompt; type `exit` to quit.

## Tests

```bash
cd backend
python -m pytest
```
