import json

from app.logging.interaction_logger import build_interaction_logger, log_interaction


def test_log_interaction_writes_json_line(tmp_path):
    logger = build_interaction_logger(log_dir=str(tmp_path))

    log_interaction(logger, "llm", "request", {"a": 1})

    log_path = tmp_path / "interactions.log"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0]) == {"source": "llm", "direction": "request", "payload": {"a": 1}}


def test_build_interaction_logger_is_idempotent_for_the_same_dir(tmp_path):
    logger_a = build_interaction_logger(log_dir=str(tmp_path))
    logger_b = build_interaction_logger(log_dir=str(tmp_path))

    assert logger_a is logger_b
    assert len(logger_a.handlers) == 1


def test_build_interaction_logger_uses_separate_files_for_different_dirs(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"

    logger_a = build_interaction_logger(log_dir=str(dir_a))
    logger_b = build_interaction_logger(log_dir=str(dir_b))

    log_interaction(logger_a, "llm", "request", {"which": "a"})
    log_interaction(logger_b, "llm", "request", {"which": "b"})

    entry_a = json.loads((dir_a / "interactions.log").read_text(encoding="utf-8").strip())
    entry_b = json.loads((dir_b / "interactions.log").read_text(encoding="utf-8").strip())
    assert entry_a["payload"] == {"which": "a"}
    assert entry_b["payload"] == {"which": "b"}
