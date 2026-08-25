import io
import json

from app.main import format_log_entry, read_log_entries, show_log


def test_format_log_entry_renders_source_direction_and_payload():
    entry = {"source": "llm", "direction": "request", "payload": {"a": 1}}

    assert format_log_entry(entry) == '[llm] request: {"a": 1}'


def test_read_log_entries_parses_json_lines_and_skips_blanks(tmp_path):
    log_path = tmp_path / "interactions.log"
    log_path.write_text(
        json.dumps({"source": "llm", "direction": "request", "payload": {}}) + "\n"
        "\n"
        + json.dumps({"source": "mcp:sales", "direction": "response", "payload": {"ok": True}}) + "\n",
        encoding="utf-8",
    )

    entries = list(read_log_entries(log_path))

    assert entries == [
        {"source": "llm", "direction": "request", "payload": {}},
        {"source": "mcp:sales", "direction": "response", "payload": {"ok": True}},
    ]


def test_show_log_prints_each_entry(tmp_path):
    log_path = tmp_path / "interactions.log"
    log_path.write_text(
        json.dumps({"source": "llm", "direction": "request", "payload": "hi"}) + "\n",
        encoding="utf-8",
    )
    out = io.StringIO()

    show_log(log_path, out=out)

    assert out.getvalue().strip() == '[llm] request: "hi"'


def test_show_log_reports_missing_log_file(tmp_path):
    missing_path = tmp_path / "does-not-exist.log"
    out = io.StringIO()

    show_log(missing_path, out=out)

    assert "No interaction log found" in out.getvalue()
