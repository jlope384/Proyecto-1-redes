"""Interactive command-line chatbot host: connects to Ollama, keeps session context, and
lets the LLM call tools exposed by multiple MCP servers (JSON-RPC over stdio or HTTP).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaClient, OllamaConnectionError
from app.logging.interaction_logger import DEFAULT_LOG_DIR, build_interaction_logger, log_interaction
from app.mcp_client.client import MCPClient
from app.mcp_client.protocol import MCPProtocolError
from app.mcp_client.registry import ToolRegistry, UnknownToolError
from app.mcp_client.transports.http import HttpTransport
from app.mcp_client.transports.stdio import StdioTransport
from app.ui.console import (
    render_banner,
    render_bot_reply,
    render_error,
    render_prompt_echo,
    render_thinking,
    render_tool_call,
    render_tool_result,
    render_user_prompt,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
GIT_REPO_DIR = WORKSPACE_DIR / "demo-repo"
DEFAULT_LOG_PATH = Path(DEFAULT_LOG_DIR) / "interactions.log"
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = (
    "You are a helpful sales assistant for a clothing store. Use the available tools "
    "to answer questions about products, stock, orders and payment links instead of guessing. "
    "You also have filesystem tools scoped to a local workspace folder, in case the user asks "
    "you to save or read a note, and git tools for a git repository, in case the user asks you "
    "to add or commit a file there. Filesystem tool paths are relative to the workspace root, "
    "so when a file is meant to be added to the repository, write it at 'demo-repo/<filename>' "
    "(not at the workspace root). For every git tool call, pass this exact string, copied "
    f"verbatim and never modified or shortened, as repo_path: {GIT_REPO_DIR} . After "
    "committing, only tell the user it succeeded if the tool result you received actually says "
    "so; if git_add reports an error, fix the repo_path (use that exact string above) and "
    "retry it before committing."
)


def connect_sales_mcp_server(logger):
    """Connect to the sales MCP server over stdio (local subprocess) by default, or over
    HTTP to a remote deployment (e.g. Cloud Run) when SALES_MCP_URL is set - same client,
    same tools/prompts/resources, only the transport changes."""
    remote_url = os.environ.get("SALES_MCP_URL")
    if remote_url:
        transport = HttpTransport(remote_url)
    else:
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


def connect_mcp_servers(connectors):
    """Call each zero-arg connector in order, returning the connected clients. If one
    raises (subprocess failed to launch, initialize() failed, ...), every client
    connected so far is closed before re-raising, so a failed startup never leaks an
    already-spawned server subprocess."""
    clients = []
    try:
        for connector in connectors:
            clients.append(connector())
        return clients
    except Exception:
        for client in clients:
            client.close()
        raise


def parse_prompt_command(text):
    """Parse a `/prompt <name> [key=value ...]` line into (name, arguments), or None if `text`
    isn't a prompt command."""
    if text != "/prompt" and not text.startswith("/prompt "):
        # A plain `startswith("/prompt")` also matched any ordinary chat message that
        # happens to start with those 7 characters (e.g. "/prompted the wrong SKU..."),
        # misparsing it as a prompt command and silently swallowing the user's real message.
        return None
    parts = text.split()[1:]
    if not parts:
        return None
    name, pairs = parts[0], parts[1:]
    arguments = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        arguments[key] = value
    return name, arguments


def prompt_text(prompt_result):
    """Flatten an MCP `prompts/get` result's messages into a single string to feed the LLM."""
    return "\n".join(m["content"]["text"] for m in prompt_result["messages"])


def extract_tool_result_text(result):
    """Flatten a `tools/call` result's `content` array into a string for the chat session.

    The MCP spec only guarantees `content` is a list of typed items - a server is free to
    return an empty list, or items that aren't `type: text` (e.g. `image`/`resource`). The
    hand-rolled sales server always returns a single text item, but the official filesystem/
    git servers are third-party code we don't control, so this can't assume that shape.
    `result` itself isn't guaranteed to be a dict either - a JSON-RPC response's "result" can
    legally be `null` or any other JSON value - so `result.get(...)` used to raise an uncaught
    AttributeError on a non-dict result instead of the placeholder text below."""
    content = (result.get("content") if isinstance(result, dict) else None) or []
    texts = [item["text"] for item in content if isinstance(item, dict) and item.get("type") == "text"]
    if texts:
        return "\n".join(texts)
    if content:
        types = ", ".join(sorted({item.get("type", "unknown") for item in content if isinstance(item, dict)}))
        return f"[tool result had no text content; type(s): {types}]"
    return "[tool returned no content]"


def handle_tool_calls(registry, tool_calls, session, logger):
    for call in tool_calls:
        try:
            name = call["function"]["name"]
        except (KeyError, TypeError) as exc:
            # A tool_calls entry from the LLM that doesn't even have a usable function name
            # (e.g. a malformed/truncated generation missing "function" or "name") used to
            # raise an uncaught KeyError/TypeError here and kill the whole chatbot session,
            # before a tool name even existed to report the error under.
            log_interaction(logger, "mcp", "error", {"call": call, "error": str(exc)})
            render_error(f"Malformed tool call from the model: {exc}")
            continue
        # `arguments` is only guaranteed present, and shaped as an object, for a well-formed
        # call. A tool with no required arguments could plausibly come back without the key at
        # all, and a malformed/truncated generation could put a non-object value there (e.g. a
        # JSON array) - either used to reach `render_tool_call`'s `arguments.items()` below with
        # something that isn't a dict, raising an uncaught AttributeError. Normalize both cases
        # to {} instead of crashing the session.
        raw_arguments = call["function"].get("arguments")
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        try:
            client = registry.client_for(name)
        except UnknownToolError as exc:
            # The LLM asked for a tool name no connected server exposes (a hallucination, or a
            # typo it made up) - report it back as a tool error instead of crashing the session.
            log_interaction(logger, "mcp", "error", {"name": name, "error": str(exc)})
            render_error(str(exc))
            session.add_tool_result(name, f"Error calling tool '{name}': {exc}")
            continue
        tag = f"mcp:{client.server_name}"
        render_tool_call(name, arguments)
        log_interaction(logger, tag, "request", {"method": "tools/call", "name": name, "arguments": arguments})
        try:
            result = client.call_tool(name, arguments)
        except (MCPProtocolError, ConnectionError) as exc:
            log_interaction(logger, tag, "error", {"name": name, "error": str(exc)})
            render_error(f"Tool call '{name}' failed: {exc}")
            session.add_tool_result(name, f"Error calling tool '{name}': {exc}")
            continue
        log_interaction(logger, tag, "response", result)
        text = extract_tool_result_text(result)
        render_tool_result(text)
        session.add_tool_result(name, text)


def run_turn(llm_client, registry, session, logger, tools):
    """Run one user turn to completion: keep calling the LLM and executing any tool calls it
    requests, feeding the results back as `role: tool` messages, until it answers with plain
    text or MAX_TOOL_ROUNDS is reached (e.g. "search for a product, then check its stock" needs
    two chained tool calls in the same turn, not just one). Returns the final reply text, or
    None if the LLM couldn't be reached (already reported to the caller)."""
    for round_num in range(MAX_TOOL_ROUNDS):
        log_interaction(logger, "llm", "request", session.history())
        try:
            with render_thinking():
                message = llm_client.chat_raw(session.history(), tools=tools)
        except OllamaConnectionError as exc:
            render_error(str(exc))
            if round_num == 0:
                session.drop_last()
            return None
        log_interaction(logger, "llm", "response", message)

        if not message.get("tool_calls"):
            reply = message.get("content", "")
            session.add_assistant_message(reply)
            return reply

        session.add_assistant_message(message.get("content", ""), tool_calls=message["tool_calls"])
        handle_tool_calls(registry, message["tool_calls"], session, logger)

    reply = "Sorry, I couldn't finish that after several tool calls - could you rephrase it?"
    session.add_assistant_message(reply)
    return reply


def format_log_entry(entry):
    source = entry.get("source", "?")
    direction = entry.get("direction", "?")
    payload = json.dumps(entry.get("payload"), ensure_ascii=False)
    return f"[{source}] {direction}: {payload}"


def read_log_entries(log_path):
    """Yield parsed JSON entries from a JSON-lines interaction log, skipping blank lines.

    A single truncated/corrupted line (e.g. the log file's writer was killed mid-write) used to
    raise an uncaught JSONDecodeError and make --show-log crash instead of showing every entry
    recorded before it; such a line is now yielded as a placeholder entry instead of skipped
    silently, so the corruption is visible rather than just an unexplained gap.
    """
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"source": "?", "direction": "?", "payload": f"<malformed log line: {line!r}>"}


def show_log(log_path=None, out=sys.stdout):
    log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
    if not log_path.is_file():
        print(f"No interaction log found at {log_path}.", file=out)
        return
    for entry in read_log_entries(log_path):
        print(format_log_entry(entry), file=out)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="MCP chatbot host")
    parser.add_argument(
        "--show-log",
        action="store_true",
        help="Print the recorded LLM/MCP interaction log and exit, instead of starting the chatbot.",
    )
    return parser.parse_args(argv)


def run():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")

    llm_client = OllamaClient()
    session = ChatSession(system_prompt=SYSTEM_PROMPT)
    logger = build_interaction_logger()

    mcp_clients = connect_mcp_servers(
        [
            lambda: connect_sales_mcp_server(logger),
            lambda: connect_filesystem_mcp_server(logger, WORKSPACE_DIR),
            lambda: connect_git_mcp_server(logger, GIT_REPO_DIR),
        ]
    )
    try:
        registry = ToolRegistry()
        for client in mcp_clients:
            registry.register(client)
        ollama_tools = registry.ollama_tools()

        render_banner(llm_client.model, [client.server_name for client in mcp_clients])
        while True:
            user_input = render_user_prompt()
            if user_input.lower() in {"exit", "quit"}:
                break
            if not user_input:
                continue

            prompt_command = parse_prompt_command(user_input)
            if prompt_command is not None:
                name, arguments = prompt_command
                try:
                    client = registry.client_for_prompt(name)
                    result = client.get_prompt(name, arguments)
                    user_input = prompt_text(result)
                except Exception as exc:  # UnknownPromptError, MCPProtocolError, bad
                    # arguments, or a malformed prompts/get result shape (e.g. a message
                    # missing "content"/"text") that would otherwise raise an uncaught
                    # KeyError straight out of prompt_text and crash the session.
                    render_error(str(exc))
                    continue
                render_prompt_echo(name, user_input)

            session.add_user_message(user_input)
            reply = run_turn(llm_client, registry, session, logger, ollama_tools)
            if reply is None:
                continue
            render_bot_reply(reply)
    finally:
        for client in mcp_clients:
            client.close()


if __name__ == "__main__":
    args = parse_args()
    if args.show_log:
        show_log()
    else:
        run()
