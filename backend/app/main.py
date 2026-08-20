"""Interactive command-line chatbot host: connects to Ollama, keeps session context, and
lets the LLM call tools exposed by the sales MCP server (JSON-RPC over stdio).
"""
import sys

from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaClient, OllamaConnectionError
from app.logging.interaction_logger import build_interaction_logger, log_interaction
from app.mcp_client.adapters import mcp_tool_to_ollama_tool
from app.mcp_client.client import MCPClient
from app.mcp_client.transports.stdio import StdioTransport

SYSTEM_PROMPT = (
    "You are a helpful sales assistant for a clothing store. Use the available tools "
    "to answer questions about products, stock, orders and payment links instead of guessing."
)


def connect_sales_mcp_server(logger):
    transport = StdioTransport("python", ["-m", "mcp_server_sales"])
    client = MCPClient(transport, server_name="sales")
    log_interaction(logger, "mcp:sales", "request", {"method": "initialize"})
    server_info = client.initialize()
    log_interaction(logger, "mcp:sales", "response", server_info)
    return client


def handle_tool_calls(mcp_client, tool_calls, session, logger):
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"]["arguments"]
        log_interaction(logger, "mcp:sales", "request", {"method": "tools/call", "name": name, "arguments": arguments})
        result = mcp_client.call_tool(name, arguments)
        log_interaction(logger, "mcp:sales", "response", result)
        text = result["content"][0]["text"]
        session.add_tool_result(name, text)


def run():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")

    llm_client = OllamaClient()
    session = ChatSession(system_prompt=SYSTEM_PROMPT)
    logger = build_interaction_logger()

    mcp_client = connect_sales_mcp_server(logger)
    ollama_tools = [mcp_tool_to_ollama_tool(spec) for spec in mcp_client.list_tools()]

    print(f"Connected to Ollama model '{llm_client.model}' and mcp-server-sales. Type 'exit' to quit.")
    try:
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue

            session.add_user_message(user_input)
            log_interaction(logger, "llm", "request", session.history())

            try:
                message = llm_client.chat_raw(session.history(), tools=ollama_tools)
            except OllamaConnectionError as exc:
                print(f"[error] {exc}")
                session.drop_last()
                continue

            log_interaction(logger, "llm", "response", message)

            if message.get("tool_calls"):
                session.add_assistant_message(message.get("content", ""), tool_calls=message["tool_calls"])
                handle_tool_calls(mcp_client, message["tool_calls"], session, logger)

                log_interaction(logger, "llm", "request", session.history())
                followup = llm_client.chat_raw(session.history())
                log_interaction(logger, "llm", "response", followup)
                reply = followup["content"]
            else:
                reply = message["content"]

            session.add_assistant_message(reply)
            print(f"Bot: {reply}")
    finally:
        mcp_client.close()


if __name__ == "__main__":
    run()
