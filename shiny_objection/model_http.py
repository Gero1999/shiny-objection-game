"""Small HTTP transport for structured model requests."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import ModelError

_RESPONSE_LIMIT = 256 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_json(url: str, data: dict, *, headers: dict | None = None, timeout: float = 30) -> dict:
    request = Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            payload = response.read(_RESPONSE_LIMIT + 1)
    except HTTPError as error:
        error.close()
        raise ModelError(f"The model server returned HTTP {error.code}. Check the connection and model name.") from None
    except (TimeoutError, URLError, OSError):
        raise ModelError("The model server is unavailable or timed out. Check the connection and retry.") from None
    try:
        if len(payload) > _RESPONSE_LIMIT:
            raise ValueError
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ModelError("The model server returned an invalid response.") from None
    return result
