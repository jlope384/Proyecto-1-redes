"""HTTP client for talking to a local Ollama server (LLM connection at the API level)."""
import os

import requests

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaConnectionError(RuntimeError):
    """Raised when the Ollama server can't be reached or returns an error."""


class OllamaClient:
    def __init__(self, model=None, base_url=None, timeout=120):
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout

    def chat_raw(self, messages, tools=None):
        """Send the full message history and return the raw assistant message (may include tool_calls)."""
        url = f"{self.base_url}/api/chat"
        payload = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise OllamaConnectionError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        return response.json()["message"]

    def chat(self, messages):
        """Send the full message history and return the assistant's reply text."""
        return self.chat_raw(messages)["content"]
