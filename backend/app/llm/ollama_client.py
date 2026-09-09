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
            data = response.json()
        except requests.exceptions.RequestException as exc:
            raise OllamaConnectionError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except ValueError as exc:
            # response.json() on a non-JSON 200 body (older requests versions raise a plain
            # json.JSONDecodeError here, a ValueError subclass, instead of a RequestException).
            raise OllamaConnectionError(
                f"Ollama at {self.base_url} returned a response that isn't valid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict) or "message" not in data:
            # A 200 response can be valid JSON without being a JSON *object* - e.g. a bare
            # `null`/number/bool body - and `"message" not in data` on a non-iterable scalar
            # (int, float, bool, None) raises an uncaught TypeError instead of the documented
            # OllamaConnectionError that run_turn relies on to keep the session alive after an
            # LLM failure. Same "don't trust external response shape" reasoning already applied
            # to the missing-"message"-key case just below.
            raise OllamaConnectionError(
                f"Ollama at {self.base_url} returned an unexpected response shape (no 'message' "
                f"key): {data!r}"
            )
        return data["message"]

    def chat(self, messages):
        """Send the full message history and return the assistant's reply text."""
        return self.chat_raw(messages)["content"]
