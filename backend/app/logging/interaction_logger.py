"""Structured logging of every request/response exchanged with the LLM and MCP servers."""
import json
import logging
import os


DEFAULT_LOG_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))


def build_interaction_logger(log_dir=None, name="interactions"):
    log_dir = log_dir or DEFAULT_LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(os.path.join(log_dir, f"{name}.log"), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    return logger


def log_interaction(logger, source, direction, payload):
    """source: 'llm' or an MCP server name. direction: 'request' or 'response'."""
    entry = {"source": source, "direction": direction, "payload": payload}
    logger.info(json.dumps(entry, ensure_ascii=False))
