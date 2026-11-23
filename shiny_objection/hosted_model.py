"""OpenAI Responses API adapter using a session-supplied token."""

from ipaddress import ip_address

from .model_http import post_json
from .models import ModelError, StructuredDialogue

DEFAULT_HOSTED_MODEL = "gpt-4.1-nano"
_ENDPOINT = "https://api.openai.com/v1/responses"


def is_local_connection(hostname: str | None, client: str | None) -> bool:
    if hostname == "localhost":
        hostname = "127.0.0.1"
    try:
        return ip_address(hostname).is_loopback and ip_address(client).is_loopback
    except ValueError:
        return False


def accepts_browser_token(scheme: str, hostname: str | None, client: str | None) -> bool:
    return scheme in ("https", "wss") or is_local_connection(hostname, client)


class OpenAIDialogue(StructuredDialogue):
    def __init__(self, api_key: str, model: str):
        token = api_key.strip()
        if not token or not token.isascii() or not token.isprintable() or " " in token:
            raise ModelError("Enter a valid OpenAI API token.")
        self.model = model.strip()
        if not self.model:
            raise ModelError("Enter an OpenAI model name.")
        self._api_key = token

    def complete(self, instruction: str, data: str, schema: dict) -> str:
        result = post_json(
            _ENDPOINT,
            {
                "model": self.model,
                "input": [
                    {"role": "developer", "content": instruction},
                    {"role": "user", "content": data},
                ],
                "text": {"format": {
                    "type": "json_schema",
                    "name": "witness_plan",
                    "strict": True,
                    "schema": schema,
                }},
                "store": False,
                "max_output_tokens": 256,
            },
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        try:
            if result["status"] != "completed":
                raise ValueError
            text = [
                part["text"] for item in result["output"] if item["type"] == "message"
                for part in item["content"] if part["type"] == "output_text"
            ]
            if len(text) == 1 and isinstance(text[0], str):
                return text[0]
        except (KeyError, TypeError, ValueError):
            pass
        raise ModelError("OpenAI did not return a complete witness plan. Try again.")
