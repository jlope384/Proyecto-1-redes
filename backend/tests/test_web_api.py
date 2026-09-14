import logging
import threading

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


def test_chat_endpoint_reports_error_event_for_malformed_prompt_result():
    """A prompts/get result missing the "content"/"text" shape prompt_text() assumes (e.g. a
    message with no "content" key) used to raise an uncaught KeyError straight through the
    /api/chat handler instead of the normal error-event response every other prompt failure
    (unknown prompt, bad arguments) already gets."""

    class MalformedPromptClient(FakeClient):
        def get_prompt(self, name, arguments):
            return {"messages": [{"role": "user"}]}

    prompt_client = MalformedPromptClient(
        "sales",
        tools=[],
        result=None,
        prompts=[{"name": "resumen_pedido", "description": "d", "arguments": []}],
    )
    llm = FakeLLM([])
    app = make_app(llm, prompt_client)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "/prompt resumen_pedido pedido_id=PED-1001"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == ""
    assert body["events"][0]["type"] == "error"
    assert llm.calls == []


def test_chat_endpoint_rejects_empty_message_without_calling_the_llm():
    # The CLI host (app/main.py) already skips an empty/whitespace-only line before doing
    # anything with it; the frontend blocks this client-side too, but that's not a
    # server-side guard - any other client posting directly to /api/chat previously burned
    # a full LLM round-trip and added a blank turn to the shared session history.
    llm = FakeLLM([])
    app = make_app(llm)

    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == ""
    assert body["events"] == []
    assert llm.calls == []


class ObservableLock:
    """Wraps a real Lock but signals `acquire_attempted` the moment a thread reaches
    `__enter__`, before it actually blocks on the underlying lock. Used only so the test
    below can deterministically know the second request has reached turn_lock (and is
    presumably blocked behind the first, still-in-progress turn) without an arbitrary
    sleep - and, crucially, without deadlocking the test itself the way waiting for the
    second request to *finish* would (it can't finish until the first turn releases the
    lock)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.acquire_attempted = threading.Event()

    def __enter__(self):
        self.acquire_attempted.set()
        self._lock.acquire()

    def __exit__(self, *exc_info):
        self._lock.release()


def test_concurrent_chat_requests_do_not_interleave_the_shared_session():
    # FastAPI runs a sync `def` route handler like chat() in a thread-pool worker, so two
    # overlapping POST /api/chat calls can genuinely run in parallel threads against the
    # one shared ChatSession. Without a lock around a whole turn, the second request's
    # add_user_message could land in the middle of the first request's still-in-progress
    # turn, corrupting the message order sent to Ollama. This test forces that overlap for
    # real, driving both requests from background threads and using events (not sleeps)
    # to pin down the exact interleaving: "first" is let in, blocks mid-turn, "second" is
    # only then started and confirmed to be genuinely contending for turn_lock (not just
    # racing to acquire it uncontended first) before "first" is allowed to finish.
    first_call_started = threading.Event()
    first_may_finish = threading.Event()

    class SlowFirstLLM(FakeLLM):
        def chat_raw(self, messages, tools=None):
            is_first_call = len(self.calls) == 0
            result = super().chat_raw(messages, tools=tools)
            if is_first_call:
                first_call_started.set()
                assert first_may_finish.wait(timeout=2), "test never released the first turn"
            return result

    llm = SlowFirstLLM(
        [
            {"role": "assistant", "content": "reply-to-first"},
            {"role": "assistant", "content": "reply-to-second"},
        ]
    )
    session = ChatSession(system_prompt="system")
    turn_lock = ObservableLock()
    app = create_app(
        llm_client=llm, registry=ToolRegistry(), session=session, logger=logging.getLogger("t"), tools=[],
        turn_lock=turn_lock,
    )
    results = {}

    def call(label, message):
        with TestClient(app) as client:
            results[label] = client.post("/api/chat", json={"message": message}).json()

    first_thread = threading.Thread(target=call, args=("first", "first"))
    first_thread.start()
    assert first_call_started.wait(timeout=2), "first request never reached the LLM call"

    second_thread = threading.Thread(target=call, args=("second", "second"))
    second_thread.start()
    # Confirms the second request is genuinely blocked behind the first (contended), not
    # just happening to run after it by luck of thread scheduling.
    assert turn_lock.acquire_attempted.wait(timeout=2), "second request never reached turn_lock"

    first_may_finish.set()
    first_thread.join(timeout=3)
    second_thread.join(timeout=3)
    assert not first_thread.is_alive() and not second_thread.is_alive()

    assert results["first"]["reply"] == "reply-to-first"
    assert results["second"]["reply"] == "reply-to-second"
    # The session must show "first" fully resolved (user + assistant) before "second"
    # even appears - not both user messages back to back, which is what an interleaved,
    # unlocked run would produce.
    turns = [(m["role"], m.get("content")) for m in session.messages[1:]]  # [1:] skips the system prompt
    assert turns == [
        ("user", "first"),
        ("assistant", "reply-to-first"),
        ("user", "second"),
        ("assistant", "reply-to-second"),
    ]


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
