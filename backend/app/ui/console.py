"""Terminal rendering for the chatbot host, built on `rich`.

The color/layout choices below follow a fixed convention applied throughout the CLI,
picked for visual hierarchy (what should draw the eye first) and standard color
psychology, not decoration:
  - cyan          -> the user's own input prompt (neutral, "your voice")
  - green         -> the assistant's reply, boxed in a panel so a turn's actual answer
                      is visually set apart from the surrounding activity log
  - dim yellow    -> background MCP tool-call activity (secondary/in-progress signal,
                      deliberately low visual weight so it doesn't compete with the
                      conversation itself)
  - bold red      -> errors (the one universal "something went wrong" color)
  - blue          -> startup/connection info (informational, non-alarming)

Every render_* function takes an optional `console` so tests can inject a Console bound
to an in-memory buffer instead of the real terminal. Dynamic content (LLM replies, tool
arguments, prompt text) is always appended to a `Text` object rather than interpolated
into a markup string, so it is never parsed as rich markup - a reply or argument value
that happens to contain square brackets must not affect styling or crash the renderer.
"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def render_banner(model_name, server_names, console=console):
    servers = ", ".join(server_names)
    body = Text()
    body.append("Model: ")
    body.append(model_name, style="bold")
    body.append("\nMCP servers: ")
    body.append(servers, style="bold")
    body.append(
        "\n\nType 'exit' to quit, or '/prompt <name> key=value ...' to start a turn "
        "from a server-provided prompt template."
    )
    console.print(Panel(body, title="MCP Chatbot", title_align="left", border_style="blue"))


def render_user_prompt(console=console, stream=None):
    """Print the styled input prompt and return the raw text the user typed.

    `stream` is forwarded to `Console.input` (read from there instead of real stdin) so
    tests can drive this without touching the process's actual standard input.
    """
    return console.input("[bold cyan]You[/bold cyan]: ", stream=stream).strip()


def render_tool_call(name, arguments, console=console):
    args_str = ", ".join(f"{key}={value!r}" for key, value in (arguments or {}).items())
    line = Text("  -> calling tool ", style="dim yellow")
    line.append(f"{name}({args_str})", style="dim yellow")
    console.print(line)


def render_bot_reply(text, console=console):
    console.print(Panel(Text(text), title="Bot", title_align="left", border_style="green"))


def render_error(text, console=console):
    line = Text()
    line.append("[error]", style="bold red")
    line.append(f" {text}")
    console.print(line)


def render_prompt_echo(name, text, console=console):
    line = Text(f"[prompt:{name}]", style="dim yellow")
    line.append(f" {text}")
    console.print(line)


def render_thinking(console=console):
    """Context manager showing a spinner while waiting on a (possibly slow) LLM call.

    Without this, the CLI gave no feedback at all between hitting enter and the reply
    appearing - a plain violation of "visibility of system status", one of the basic
    usability heuristics the assignment asks this UI to apply.
    """
    return console.status("[cyan]Thinking...[/cyan]", spinner="dots")
