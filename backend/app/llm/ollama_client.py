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

    def chat(self, messages):
        """Send the full message history and return the assistant's reply text."""
        url = f"{self.base_url}/api/chat"
        payload = {"model": self.model, "messages": messages, "stream": False}
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise OllamaConnectionError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        return response.json()["message"]["content"]
