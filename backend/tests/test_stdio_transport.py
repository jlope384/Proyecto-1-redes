import subprocess
from unittest.mock import MagicMock, patch

from app.mcp_client.transports.stdio import StdioTransport


def _make_transport(fake_process):
    with patch("app.mcp_client.transports.stdio.subprocess.Popen", return_value=fake_process):
        return StdioTransport("fake-cmd")


def test_receive_parses_json_line():
    fake_process = MagicMock()
    fake_process.stdout.readline.return_value = '{"jsonrpc": "2.0", "id": 1, "result": {}}\n'
    transport = _make_transport(fake_process)

    assert transport.receive() == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_receive_raises_connection_error_on_closed_stdout():
    fake_process = MagicMock()
    fake_process.stdout.readline.return_value = ""
    fake_process.stderr.read.return_value = "server crashed"
    transport = _make_transport(fake_process)

    try:
        transport.receive()
    except ConnectionError as exc:
        assert "server crashed" in str(exc)
        return
    assert False, "expected ConnectionError"


def test_receive_raises_connection_error_on_non_json_line():
    # A stray non-JSON line on stdout (e.g. a first-run banner from a server launched via
    # npx/uvx) previously crashed the whole chatbot with an uncaught json.JSONDecodeError.
    fake_process = MagicMock()
    fake_process.stdout.readline.return_value = "npm notice: something\n"
    transport = _make_transport(fake_process)

    try:
        transport.receive()
    except ConnectionError as exc:
        assert "npm notice" in str(exc)
        return
    assert False, "expected ConnectionError, not an uncaught JSONDecodeError"


def test_close_terminates_process_that_exits_promptly():
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    transport = _make_transport(fake_process)

    transport.close()

    fake_process.terminate.assert_called_once()
    fake_process.wait.assert_called_once_with(timeout=5)
    fake_process.kill.assert_not_called()


def test_close_kills_process_that_ignores_terminate():
    # A subprocess that doesn't exit within the terminate() timeout previously raised
    # TimeoutExpired out of close(), which (uncaught by the caller's cleanup loop) would
    # skip closing every other connected MCP server after it.
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    fake_process.wait.side_effect = [subprocess.TimeoutExpired(cmd="fake", timeout=5), None]
    transport = _make_transport(fake_process)

    transport.close()

    fake_process.terminate.assert_called_once()
    fake_process.kill.assert_called_once()
    assert fake_process.wait.call_count == 2


def test_close_is_a_noop_if_process_already_exited():
    fake_process = MagicMock()
    fake_process.poll.return_value = 0
    transport = _make_transport(fake_process)

    transport.close()

    fake_process.terminate.assert_not_called()


def test_init_resolves_command_via_shutil_which():
    # On Windows, `npx`/`uvx` are `.cmd` shims that subprocess.Popen can't exec directly
    # without going through a shell - shutil.which() resolves the real executable path
    # (with its PATHEXT-matched extension) so Popen can launch it directly on any OS.
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    with patch("app.mcp_client.transports.stdio.shutil.which", return_value=r"C:\nodejs\npx.cmd"):
        with patch("app.mcp_client.transports.stdio.subprocess.Popen", return_value=fake_process) as popen:
            StdioTransport("npx", ["-y", "some-package"])

    args, kwargs = popen.call_args
    assert args[0][0] == r"C:\nodejs\npx.cmd"


def test_init_falls_back_to_raw_command_if_not_found_on_path():
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    with patch("app.mcp_client.transports.stdio.shutil.which", return_value=None):
        with patch("app.mcp_client.transports.stdio.subprocess.Popen", return_value=fake_process) as popen:
            StdioTransport("some-missing-command")

    args, kwargs = popen.call_args
    assert args[0][0] == "some-missing-command"
