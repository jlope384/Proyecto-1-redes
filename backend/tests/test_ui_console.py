import io

from rich.console import Console

from app.ui.console import (
    TOOL_RESULT_MAX_CHARS,
    render_banner,
    render_bot_reply,
    render_demo_step,
    render_error,
    render_prompt_echo,
    render_thinking,
    render_tool_call,
    render_tool_result,
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


def test_render_tool_result_shows_the_result_text():
    console, buffer = make_console()

    render_tool_result("3 productos encontrados", console=console)

    out = buffer.getvalue()
    assert "3 productos encontrados" in out


def test_render_tool_result_truncates_long_payloads():
    console, buffer = make_console()

    render_tool_result("x" * (TOOL_RESULT_MAX_CHARS + 50), console=console)

    # rich word-wraps the line at the console width, so compare with wrapping removed
    # rather than assuming the truncated text survives as one unbroken substring.
    out = buffer.getvalue().replace("\n", "")
    assert "x" * TOOL_RESULT_MAX_CHARS in out
    assert "..." in out
    assert "x" * (TOOL_RESULT_MAX_CHARS + 1) not in out


def test_render_demo_step_shows_label_and_raw_value_unmodified():
    console, buffer = make_console()

    render_demo_step(
        "tools/call buscar_productos",
        {"content": [{"type": "text", "text": "3 hits"}]},
        console=console,
    )

    out = buffer.getvalue()
    assert "tools/call buscar_productos" in out
    assert "{'content': [{'type': 'text', 'text': '3 hits'}]}" in out


def test_render_prompt_echo_shows_name_and_text():
    console, buffer = make_console()

    render_prompt_echo("resumen_pedido", "Resume el pedido PED-1001", console=console)

    out = buffer.getvalue()
    assert "[prompt:resumen_pedido]" in out
    assert "Resume el pedido PED-1001" in out


def test_render_thinking_is_a_usable_context_manager_around_slow_work():
    console, _buffer = make_console()
    ran = []

    with render_thinking(console=console):
        ran.append("llm call happened")

    assert ran == ["llm call happened"]


def test_render_user_prompt_reads_from_injected_stream_and_strips_whitespace():
    console, buffer = make_console()
    stream = io.StringIO("  hola chatbot  \n")

    result = render_user_prompt(console=console, stream=stream)

    assert result == "hola chatbot"
    assert "You" in buffer.getvalue()
