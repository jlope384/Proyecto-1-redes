import logging

from fastapi.testclient import TestClient

from app.chat.session import ChatSession
from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import ToolRegistry
from app.web.api import create_app, events_since


class FakeLLM:
    """Same fake used by tests/test_run_turn.py: scripted chat_raw responses."""

    def __init__(self, responses, model="fake-model"):
        self._responses = list(responses)
        self.model = model
        self.calls = []

    def chat_raw(self, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, server_name, tools, result, prompts=None):
        self.server_name = server_name
        self._tools = tools
        self._result = result
        self._prompts = prompts or []
        self.calls = []

    def list_tools(self):
        return self._tools

    def list_prompts(self):
        if not self._prompts:
            raise MCPProtocolError(-32601, "Method not found: prompts/list")
        return self._prompts

    def get_prompt(self, name, arguments):
        return {"messages": [{"role": "user", "content": {"type": "text", "text": f"prompt:{name}:{arguments}"}}]}

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return self._result

    def close(self):
        pass


def make_app(llm_client, client=None):
    registry = ToolRegistry()
    if client is not None:
        registry.register(client)
    session = ChatSession(system_prompt="system")
    logger = logging.getLogger("test-web-api")
    return create_app(
        llm_client=llm_client,
        registry=registry,
        session=session,
        logger=logger,
        tools=registry.ollama_tools(),
        mcp_clients=[client] if client is not None else [],
    )


def test_chat_endpoint_returns_plain_reply_with_no_events():
    llm = FakeLLM([{"role": "assistant", "content": "hi there"}])
    app = make_app(llm)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "hi there"
    assert body["events"] == []


def test_chat_endpoint_reports_tool_call_and_result_events():
    tool_client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "text", "text": "camisa azul, $249"}]},
    )
    llm = FakeLLM(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "buscar_productos", "arguments": {"query": "camisa azul"}}}],
            },
            {"role": "assistant", "content": "Tenemos una camisa azul a $249."},
        ]
    )
    app = make_app(llm, tool_client)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "tienen camisas azules?"})

    body = response.json()
    assert body["reply"] == "Tenemos una camisa azul a $249."
    assert body["events"] == [
        {"type": "tool_call", "name": "buscar_productos", "arguments": {"query": "camisa azul"}},
        {"type": "tool_result", "name": "buscar_productos", "text": "camisa azul, $249"},
    ]


def test_chat_endpoint_reports_error_event_when_llm_unreachable():
    from app.llm.ollama_client import OllamaConnectionError

    llm = FakeLLM([OllamaConnectionError("no ollama")])
    app = make_app(llm)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "hello"})

    body = response.json()
    assert body["reply"] == ""
    assert body["events"][0]["type"] == "error"


def test_chat_endpoint_resolves_a_slash_prompt_command():
    prompt_client = FakeClient(
        "sales",
        tools=[],
        result=None,
        prompts=[{"name": "resumen_pedido", "description": "d", "arguments": []}],
    )
    llm = FakeLLM([{"role": "assistant", "content": "aqui esta el resumen"}])
    app = make_app(llm, prompt_client)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "/prompt resumen_pedido pedido_id=PED-1001"})

    body = response.json()
    assert body["events"][0]["type"] == "prompt"
    assert body["events"][0]["name"] == "resumen_pedido"
    assert "PED-1001" in body["events"][0]["text"]
    assert body["reply"] == "aqui esta el resumen"


def test_servers_endpoint_lists_model_and_connected_servers():
    tool_client = FakeClient("sales", tools=[], result=None)
    llm = FakeLLM([])
    app = make_app(llm, tool_client)

    with TestClient(app) as client:
        response = client.get("/api/servers")

    assert response.json() == {"model": "fake-model", "servers": ["sales"]}


def test_events_since_ignores_messages_before_start_index():
    session = ChatSession()
    session.add_user_message("first turn, not part of the reconstructed events")
    start_index = len(session.messages)
    session.add_assistant_message("", tool_calls=[{"function": {"name": "buscar_productos", "arguments": {}}}])
    session.add_tool_result("buscar_productos", "ok")

    events = events_since(session, start_index)

    assert events == [
        {"type": "tool_call", "name": "buscar_productos", "arguments": {}},
        {"type": "tool_result", "name": "buscar_productos", "text": "ok"},
    ]
