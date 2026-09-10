"""Tests for `mcp_server_sales/__main__.py`'s `parse_args()`: the CLI entry point used both
for local manual testing (`python -m mcp_server_sales --transport http`) and, unmodified, as
the Cloud Run container entrypoint (see docs/spec/mcp_server_sales.md, "Remote deployment").
Cloud Run injects HOST/PORT-shaped configuration only via the PORT env var, so the env-var
defaults here are real, load-bearing behavior, not just argparse boilerplate - previously
untested.
"""
from mcp_server_sales.__main__ import parse_args


def test_defaults_to_stdio_transport():
    args = parse_args([])

    assert args.transport == "stdio"


def test_http_transport_defaults_host_and_port_without_env(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    args = parse_args(["--transport", "http"])

    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 8765


def test_http_transport_reads_host_and_port_from_env(monkeypatch):
    # This is exactly the shape Cloud Run uses: it injects PORT (commonly 8080) and requires
    # the process to listen on 0.0.0.0, with no CLI flags passed at all.
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8080")

    args = parse_args(["--transport", "http"])

    assert args.host == "0.0.0.0"
    assert args.port == 8080


def test_explicit_cli_flags_override_env(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8080")

    args = parse_args(["--transport", "http", "--host", "127.0.0.1", "--port", "9000"])

    assert args.host == "127.0.0.1"
    assert args.port == 9000


def test_unknown_transport_is_rejected():
    try:
        parse_args(["--transport", "carrier-pigeon"])
    except SystemExit:
        return
    assert False, "expected argparse to reject an unknown --transport choice"
