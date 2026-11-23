"""Shared limits for player and rival dialogue."""

from .errors import GameError


LEAD_LIMIT = 240
QUESTION_LIMIT = 400
CLOSING_LIMIT = 480


def bounded(text: str, limit: int) -> str:
    text = text.strip()
    if not text:
        raise GameError("Write a message first.")
    if len(text) > limit:
        raise GameError(f"Keep your message to {limit} characters.")
    return text
