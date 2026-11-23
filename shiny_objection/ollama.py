"""Ollama connection at an operator-configured endpoint."""

from urllib.parse import urlsplit

from .model_http import post_json
from .models import ModelError, StructuredDialogue

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "smollm2:135m"


class OllamaDialogue(StructuredDialogue):
    def __init__(self, model: str, base_url: str = DEFAULT_OLLAMA_URL):
        self.model = model.strip()
        if not self.model:
            raise ModelError("Enter the name of an installed Ollama model.")
        try:
            url = urlsplit(base_url)
            _ = url.port
        except ValueError:
            raise ModelError("The configured Ollama endpoint is invalid.") from None
        if (
            url.scheme not in ("http", "https") or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment
        ):
            raise ModelError("The configured Ollama endpoint is invalid.")
        self._endpoint = base_url.rstrip("/") + "/api/chat"

    def complete(self, instruction: str, data: str, schema: dict) -> str:
        result = post_json(self._endpoint, {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": data},
            ],
            "format": schema,
            "options": {"temperature": 0, "num_predict": 128},
            "stream": False,
        })
        try:
            content = result["message"]["content"]
            if not isinstance(content, str) or not content:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ModelError("Ollama did not return a witness plan.") from None
        return content
