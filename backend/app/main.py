"""Interactive command-line chatbot host: connects to Ollama, keeps session context, and
lets the LLM call tools exposed by multiple MCP servers (JSON-RPC over stdio).
"""
import subprocess
import sys
from pathlib import Path

from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaClient, OllamaConnectionError
from app.logging.interaction_logger import build_interaction_logger, log_interaction
from app.mcp_client.client import MCPClient
from app.mcp_client.registry import ToolRegistry
from app.mcp_client.transports.stdio import StdioTransport

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
GIT_REPO_DIR = WORKSPACE_DIR / "demo-repo"

SYSTEM_PROMPT = (
    "You are a helpful sales assistant for a clothing store. Use the available tools "
    "to answer questions about products, stock, orders and payment links instead of guessing. "
    "You also have filesystem tools scoped to a local workspace folder, in case the user asks "
    f"you to save or read a note, and git tools for the repository at {GIT_REPO_DIR}, in case "
    "the user asks you to add or commit a file there."
)


def connect_sales_mcp_server(logger):
    transport = StdioTransport("python", ["-m", "mcp_server_sales"])
    client = MCPClient(transport, server_name="sales")
    log_interaction(logger, "mcp:sales", "request", {"method": "initialize"})
    server_info = client.initialize()
    log_interaction(logger, "mcp:sales", "response", server_info)
    return client


def connect_filesystem_mcp_server(logger, workspace_dir):
    workspace_dir.mkdir(parents=True, exist_ok=True)
    transport = StdioTransport("npx", ["-y", "@modelcontextprotocol/server-filesystem", str(workspace_dir)])
    client = MCPClient(transport, server_name="filesystem")
    log_interaction(logger, "mcp:filesystem", "request", {"method": "initialize"})
    server_info = client.initialize()
    log_interaction(logger, "mcp:filesystem", "response", server_info)
    return client


def ensure_git_repo(repo_path):
    """The official git MCP server has no git_init tool, so the host bootstraps the demo
    repository itself the first time it connects (a no-op on later runs)."""
    repo_path.mkdir(parents=True, exist_ok=True)
    if not (repo_path / ".git").is_dir():
        subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True, text=True)


def connect_git_mcp_server(logger, repo_path):
    ensure_git_repo(repo_path)
    transport = StdioTransport("uvx", ["mcp-server-git"])
    client = MCPClient(transport, server_name="git")
    log_interaction(logger, "mcp:git", "request", {"method": "initialize"})
    server_info = client.initialize()
    log_interaction(logger, "mcp:git", "response", server_info)
    return client


def handle_tool_calls(registry, tool_calls, session, logger):
    for call in tool_calls:
        name = call["function"]["name"]
        arguments = call["function"]["arguments"]
        client = registry.client_for(name)
        tag = f"mcp:{client.server_name}"
        log_interaction(logger, tag, "request", {"method": "tools/call", "name": name, "arguments": arguments})
        result = client.call_tool(name, arguments)
        log_interaction(logger, tag, "response", result)
        text = result["content"][0]["text"]
        session.add_tool_result(name, text)


def run():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")

    llm_client = OllamaClient()
    session = ChatSession(system_prompt=SYSTEM_PROMPT)
    logger = build_interaction_logger()

    sales_client = connect_sales_mcp_server(logger)
    filesystem_client = connect_filesystem_mcp_server(logger, WORKSPACE_DIR)
    git_client = connect_git_mcp_server(logger, GIT_REPO_DIR)
    mcp_clients = [sales_client, filesystem_client, git_client]

    registry = ToolRegistry()
    for client in mcp_clients:
        registry.register(client)
    ollama_tools = registry.ollama_tools()

    print(
        f"Connected to Ollama model '{llm_client.model}', mcp-server-sales, the filesystem MCP "
        "server and the git MCP server. Type 'exit' to quit."
    )
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
                handle_tool_calls(registry, message["tool_calls"], session, logger)

                log_interaction(logger, "llm", "request", session.history())
                followup = llm_client.chat_raw(session.history())
                log_interaction(logger, "llm", "response", followup)
                reply = followup["content"]
            else:
                reply = message["content"]

            session.add_assistant_message(reply)
            print(f"Bot: {reply}")
    finally:
        for client in mcp_clients:
            client.close()


if __name__ == "__main__":
    run()
