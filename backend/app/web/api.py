"""FastAPI web host for the chatbot: the same session/registry/tool-calling logic
`app/main.py`'s terminal host uses, exposed as a small JSON API for `frontend/public/` instead
of a terminal loop. Not an MCP SDK or MCP transport - this is the *host* layer only, sitting on
top of the hand-rolled MCP client the same way `app/main.py` does.

Reuses `app.main.run_turn` (and the connector functions) as-is rather than re-implementing the
tool-calling loop, so this new surface can't drift from the already-tested CLI behavior. The
only new piece is `events_since`, which reconstructs a JSON-friendly list of "a tool was called
/ here's its result" events from the messages a turn appended to the session - `run_turn` never
needed to expose that shape itself, since the CLI renders each event live as it happens instead
of collecting them.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaClient
from app.logging.interaction_logger import build_interaction_logger
from app.main import (
    GIT_REPO_DIR,
    SYSTEM_PROMPT,
    WORKSPACE_DIR,
    connect_filesystem_mcp_server,
    connect_git_mcp_server,
    connect_mcp_servers,
    connect_sales_mcp_server,
    parse_prompt_command,
    prompt_text,
    run_turn,
)
from app.mcp_client.registry import ToolRegistry

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend" / "public"


class ChatRequest(BaseModel):
    message: str


class ChatEvent(BaseModel):
    type: str
    name: str | None = None
    arguments: dict | None = None
    text: str | None = None


class ChatResponse(BaseModel):
    reply: str
    events: list[ChatEvent]


def events_since(session, start_index):
    """Turn the session messages a single turn appended (from `start_index` onward) into a
    JSON-friendly event list for the frontend: one `tool_call` event per tool the model asked
    to invoke, and one `tool_result` event per matching `role: tool` message with its result.
    Both `add_assistant_message`/`add_tool_result` already store this on the session for the
    LLM's own benefit - this just reads it back instead of duplicating handle_tool_calls' logic.
    """
    events = []
    for message in session.messages[start_index:]:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            for call in message["tool_calls"]:
                function = call.get("function") if isinstance(call, dict) else None
                if isinstance(function, dict):
                    events.append(
                        {
                            "type": "tool_call",
                            "name": function.get("name"),
                            "arguments": function.get("arguments") or {},
                        }
                    )
        elif message.get("role") == "tool":
            events.append({"type": "tool_result", "name": message.get("name"), "text": message.get("content", "")})
    return events


def create_app(llm_client=None, registry=None, session=None, logger=None, tools=None, mcp_clients=None, connectors=None):
    """App factory. Production use (`python -m app.web`) calls this with no arguments, so the
    lifespan below connects everything for real on startup - exactly like `app.main.run()`
    does. Tests pass fakes for `llm_client`/`registry`/`session`/`logger`/`tools` directly,
    which skips real connections entirely (no subprocess, no network) while still exercising
    the actual request-handling code below."""
    state = {
        "llm_client": llm_client,
        "registry": registry,
        "session": session,
        "logger": logger,
        "tools": tools,
        "mcp_clients": mcp_clients or [],
    }

    @asynccontextmanager
    async def lifespan(app):
        if state["llm_client"] is None:
            state["llm_client"] = OllamaClient()
            state["session"] = ChatSession(system_prompt=SYSTEM_PROMPT)
            state["logger"] = build_interaction_logger()
            state["mcp_clients"] = connect_mcp_servers(
                connectors
                or [
                    lambda: connect_sales_mcp_server(state["logger"]),
                    lambda: connect_filesystem_mcp_server(state["logger"], WORKSPACE_DIR),
                    lambda: connect_git_mcp_server(state["logger"], GIT_REPO_DIR),
                ]
            )
            registry_ = ToolRegistry()
            for client in state["mcp_clients"]:
                registry_.register(client)
            state["registry"] = registry_
            state["tools"] = registry_.ollama_tools()
        try:
            yield
        finally:
            for client in state["mcp_clients"]:
                client.close()

    app = FastAPI(title="MCP Sales Chatbot", lifespan=lifespan)

    @app.get("/api/servers")
    def servers():
        return {
            "model": state["llm_client"].model if state["llm_client"] else None,
            "servers": [client.server_name for client in state["mcp_clients"]],
        }

    @app.post("/api/chat", response_model=ChatResponse, response_model_exclude_none=True)
    def chat(request: ChatRequest):
        session = state["session"]
        text = request.message
        events = []

        prompt_command = parse_prompt_command(text)
        if prompt_command is not None:
            name, arguments = prompt_command
            try:
                prompt_client = state["registry"].client_for_prompt(name)
                result = prompt_client.get_prompt(name, arguments)
                text = prompt_text(result)
            except Exception as exc:  # UnknownPromptError, MCPProtocolError, bad
                # arguments, or a malformed prompts/get result shape (e.g. a message
                # missing "content"/"text") that would otherwise raise an uncaught
                # KeyError straight out of prompt_text.
                return ChatResponse(reply="", events=[{"type": "error", "text": str(exc)}])
            events.append({"type": "prompt", "name": name, "text": text})

        start_index = len(session.messages)
        session.add_user_message(text)
        reply = run_turn(state["llm_client"], state["registry"], session, state["logger"], state["tools"])
        events += events_since(session, start_index + 1)
        if reply is None:
            events.append({"type": "error", "text": "Could not reach the LLM. Check that Ollama is running."})
            return ChatResponse(reply="", events=events)
        return ChatResponse(reply=reply, events=events)

    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app


app = create_app()
