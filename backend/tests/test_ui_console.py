import io

from rich.console import Console

from app.ui.console import (
    render_banner,
    render_bot_reply,
    render_error,
    render_prompt_echo,
    render_tool_call,
    render_user_prompt,
)


def make_console():
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    return console, buffer


def test_render_banner_lists_model_and_servers():
    console, buffer = make_console()

    render_banner("llama3", ["sales", "filesystem", "git"], console=console)

    out = buffer.getvalue()
    assert "llama3" in out
    assert "sales, filesystem, git" in out
    assert "/prompt" in out


def test_render_bot_reply_shows_text_and_bot_label():
    console, buffer = make_console()

    render_bot_reply("Hello, how can I help?", console=console)

    out = buffer.getvalue()
    assert "Bot" in out
    assert "Hello, how can I help?" in out


def test_render_error_keeps_the_error_prefix():
    console, buffer = make_console()

    render_error("Tool call 'buscar_productos' failed: boom", console=console)

    out = buffer.getvalue()
    assert "[error]" in out
    assert "Tool call 'buscar_productos' failed: boom" in out


def test_render_tool_call_shows_name_and_arguments():
    console, buffer = make_console()

    render_tool_call("buscar_productos", {"query": "camisa"}, console=console)

    out = buffer.getvalue()
    assert "buscar_productos" in out
    assert "query='camisa'" in out


def test_render_tool_call_handles_no_arguments():
    console, buffer = make_console()

    render_tool_call("consultar_inventario", None, console=console)

    out = buffer.getvalue()
    assert "consultar_inventario()" in out


def test_render_prompt_echo_shows_name_and_text():
    console, buffer = make_console()

    render_prompt_echo("resumen_pedido", "Resume el pedido PED-1001", console=console)

    out = buffer.getvalue()
    assert "[prompt:resumen_pedido]" in out
    assert "Resume el pedido PED-1001" in out


def test_render_user_prompt_reads_from_injected_stream_and_strips_whitespace():
    console, buffer = make_console()
    stream = io.StringIO("  hola chatbot  \n")

    result = render_user_prompt(console=console, stream=stream)

    assert result == "hola chatbot"
    assert "You" in buffer.getvalue()
