"""Structured question interpretation for the offline playthrough."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .cases import Ground, Statement
from .game import mentions, words


@dataclass(frozen=True)
class QuestionPlan:
    statement_id: str | None
    grounds: tuple[Ground, ...] = ()


class Dialogue(Protocol):
    def interpret(self, question: str, eligible: Mapping[str, Statement]) -> QuestionPlan:
        """Match the question to an already eligible authored statement."""


class ScriptedDialogue:
    """Deterministic keyword matching for a run without model credentials."""

    def interpret(self, question: str, eligible: Mapping[str, Statement]) -> QuestionPlan:
        normalized = words(question)
        matches = [
            (key, sum(mentions(normalized, topic) for topic in statement.topics))
            for key, statement in eligible.items()
        ]
        best, score = max(matches, key=lambda match: match[1], default=(None, 0))
        grounds = []
        if any(normalized.endswith(f" {phrase}") for phrase in (
            "correct", "right", "didn t you", "couldn t you", "did you", "could you",
        )):
            grounds.append(Ground.LEADING)
        if any(mentions(normalized, phrase) for phrase in ("think", "guess", "assume", "suppose")):
            grounds.append(Ground.SPECULATION)
        if best is not None and score and eligible[best].notice_purpose:
            grounds.append(Ground.HEARSAY)
        if not score:
            grounds.append(Ground.RELEVANCE)
        return QuestionPlan(best if score else None, tuple(grounds))
