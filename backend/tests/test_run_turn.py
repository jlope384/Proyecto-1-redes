import logging

from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaConnectionError
from app.main import MAX_TOOL_ROUNDS, run_turn
from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import ToolRegistry


class FakeLLM:
    """Stands in for OllamaClient.chat_raw, returning one scripted message per call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def chat_raw(self, messages, tools=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, server_name, tools, result):
        self.server_name = server_name
        self._tools = tools
        self._result = result
        self.calls = []

    def list_tools(self):
        return self._tools

    def list_prompts(self):
        raise MCPProtocolError(-32601, "Method not found: prompts/list")

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return self._result


def make_registry(client):
    registry = ToolRegistry()
    registry.register(client)
    return registry


def tool_call(name):
    return {"function": {"name": name, "arguments": {}}}


def test_run_turn_returns_plain_text_reply_without_any_tool_call():
    llm = FakeLLM([{"role": "assistant", "content": "hi there"}])
    session = ChatSession()
    session.add_user_message("hello")
    logger = logging.getLogger("test-run-turn-plain")

    reply = run_turn(llm, ToolRegistry(), session, logger, tools=[])

    assert reply == "hi there"
    assert session.messages[-1] == {"role": "assistant", "content": "hi there"}


def test_run_turn_chains_two_rounds_of_tool_calls_in_one_turn():
    client = FakeClient(
        "sales",
        [
            {"name": "buscar_productos", "description": "d", "inputSchema": {}},
            {"name": "consultar_inventario", "description": "d", "inputSchema": {}},
        ],
        result={"content": [{"type": "text", "text": "ok"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    session.add_user_message("busca camisas y revisa el inventario")
    logger = logging.getLogger("test-run-turn-chain")

    llm = FakeLLM(
        [
            {"role": "assistant", "content": "", "tool_calls": [tool_call("buscar_productos")]},
            {"role": "assistant", "content": "", "tool_calls": [tool_call("consultar_inventario")]},
            {"role": "assistant", "content": "listo"},
        ]
    )

    reply = run_turn(llm, registry, session, logger, tools=registry.ollama_tools())

    assert reply == "listo"
    assert [called_name for called_name, _ in client.calls] == ["buscar_productos", "consultar_inventario"]
    # every round, including follow-ups, must still offer the tool list - not just the first call.
    assert all(call["tools"] for call in llm.calls)


def test_run_turn_stops_after_max_tool_rounds_instead_of_looping_forever():
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "text", "text": "ok"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    session.add_user_message("busca")
    logger = logging.getLogger("test-run-turn-max-rounds")

    always_tool_call = {"role": "assistant", "content": "", "tool_calls": [tool_call("buscar_productos")]}
    llm = FakeLLM([always_tool_call] * 10)

    reply = run_turn(llm, registry, session, logger, tools=registry.ollama_tools())

    assert reply is not None
    assert len(llm.calls) == MAX_TOOL_ROUNDS
    assert len(client.calls) == MAX_TOOL_ROUNDS


def test_run_turn_reports_connection_error_and_drops_user_message_on_first_round():
    llm = FakeLLM([OllamaConnectionError("no ollama")])
    session = ChatSession()
    session.add_user_message("hello")
    logger = logging.getLogger("test-run-turn-connection-error")

    reply = run_turn(llm, ToolRegistry(), session, logger, tools=[])

    assert reply is None
    assert session.messages == []


def test_run_turn_reports_connection_error_on_a_later_round_without_crashing():
    client = FakeClient(
        "sales",
        [{"name": "buscar_productos", "description": "d", "inputSchema": {}}],
        result={"content": [{"type": "text", "text": "ok"}]},
    )
    registry = make_registry(client)
    session = ChatSession()
    session.add_user_message("busca")
    logger = logging.getLogger("test-run-turn-connection-error-later")

    llm = FakeLLM(
        [
            {"role": "assistant", "content": "", "tool_calls": [tool_call("buscar_productos")]},
            OllamaConnectionError("no ollama"),
        ]
    )

    reply = run_turn(llm, registry, session, logger, tools=registry.ollama_tools())

    assert reply is None
    # the earlier, successful round's messages are real interactions and are kept.
    assert session.messages[-1]["role"] == "tool"
