"""Tests for mcp_server_sales.core.server.serve(), the stdio read/dispatch loop itself
(as opposed to handle_message(), which the rest of test_mcp_server_sales.py covers)."""
import io
import json
import sys

from mcp_server_sales.core.server import serve


def test_serve_reports_parse_error_for_malformed_line_and_keeps_running(monkeypatch):
    stdin = io.StringIO("not valid json\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "stdout", stdout)

    serve()

    lines = [json.loads(line) for line in stdout.getvalue().strip().splitlines()]
    assert lines[0]["error"]["code"] == -32700
    assert lines[0]["id"] is None
    # the malformed line didn't kill the loop - the next, valid line was still handled
    assert lines[1]["id"] == 1
    assert "tools" in lines[1]["result"]
