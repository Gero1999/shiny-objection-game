"""The courtroom turn order, objection rules, and admitted record."""

import random
import re
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from . import chat
from .cases import Examination, Ground, ScriptedMove, Side, Statement
from .game import Game, GameError, Phase, mentions, words
from .models import Dialogue, QuestionPlan, ScriptedDialogue


class Kind(StrEnum):
    QUESTION = "question"
    EXHIBIT = "exhibit"
    ANSWER = "answer"


class Status(StrEnum):
    SPOKEN = "spoken"
    RULING = "ruling"
    ADMITTED = "admitted"
    LIMITED = "limited to notice"
    EXCLUDED = "excluded"
    STRUCK = "struck"
    SHOWN = "shown to witness"


@dataclass(frozen=True)
class Turn:
    witness_id: str
    calling_side: Side
    examination: Examination

    @property
    def acting_side(self) -> Side:
        return self.calling_side if self.examination == Examination.DIRECT else self.calling_side.other


@dataclass(frozen=True)
class Move:
    kind: Kind
    text: str
    exhibit_id: str | None = None
    statement_id: str | None = None
    grounds: tuple[Ground, ...] = ()


@dataclass(frozen=True)
class Pending:
    move: Move
    objection: Ground | None = None
    notice_only: bool = False


@dataclass(frozen=True)
class RecordEntry:
    number: int
    speaker: str
    text: str
    status: Status
    proof_id: str | None = None
    witness_id: str | None = None
    kind: Kind | None = None


@dataclass(frozen=True)
class QuestionRequest:
    question: str
    eligible: Mapping[str, Statement]
    context: tuple[str, ...]
    stamp: tuple[object, int, int]


_GROUND_REASONS = {
    Ground.LEADING: "The question suggests its answer on direct examination.",
    Ground.HEARSAY: "The statement is being offered to prove what someone else said.",
    Ground.SPECULATION: "The question calls for a guess outside the witness's knowledge.",
    Ground.RELEVANCE: "The move has no supported connection to this hearing.",
    Ground.FOUNDATION: "The exhibit's required foundation is missing from the record.",
}


class Trial:
    def __init__(self, game: Game, dialogue: Dialogue | None = None):
        if game.phase != Phase.TRIAL or game.side is None:
            raise GameError("Choose your witness before starting the trial.")
        self.case = game.case
        self.side = game.side
        self.exhibits = game.trial_exhibits()
        self.dialogue = dialogue or ScriptedDialogue()
        lineups = {self.side: game.player_lineup, self.side.other: game.rival_lineup}
        self.turns = tuple(
            Turn(witness, side, examination)
            for side in Side
            for witness in lineups[side]
            for examination in Examination
        )
        self._turn_index = 0
        self._question_owner = object()
        self.pending: Pending | None = None
        self.record: list[RecordEntry] = []
        self._shown: dict[str, set[str]] = {key: set() for key in self.case.witnesses}
        self._rival_exhibits = set(self.case.opening_exhibits + self.case.rival_exhibits[self.side.other])
        candidates = [
            index for index, turn in enumerate(self.turns)
            if turn.acting_side != self.side and turn.examination in self.case.witnesses[turn.witness_id].departures
        ]
        self._departure_turn = random.Random(game.seed).choice(candidates) if candidates else None
        self._queue: deque[ScriptedMove] = deque()
        self._prepare_turn()

    @property
    def turn(self) -> Turn | None:
        return self.turns[self._turn_index] if self._turn_index < len(self.turns) else None

    @property
    def player_turn(self) -> bool:
        return self.turn is not None and self.turn.acting_side == self.side

    @property
    def admitted_ids(self) -> frozenset[str]:
        return frozenset(
            entry.proof_id for entry in self.record
            if entry.proof_id is not None and entry.status == Status.ADMITTED
        )

    def ask(self, question: str) -> None:
        request = self.prepare_question(question)
        self.apply_question(request, self.dialogue.interpret(
            request.question, request.eligible, request.context,
        ))

    def prepare_question(self, question: str) -> QuestionRequest:
        turn = self._require_turn(player=True)
        question = chat.bounded(question, chat.QUESTION_LIMIT)
        context = tuple(
            f"{entry.speaker}: {entry.text}" for entry in self.record
            if entry.witness_id == turn.witness_id and entry.kind is not None
            and entry.status in (Status.SPOKEN, Status.ADMITTED, Status.LIMITED, Status.SHOWN)
        )[-6:]
        demeanor = self.case.witnesses[turn.witness_id].demeanor
        if demeanor:
            context = (f"Witness demeanor: {demeanor}", *context)
        return QuestionRequest(
            question, MappingProxyType(self._eligible_statements()), context, self._question_stamp(),
        )

    def apply_question(self, request: QuestionRequest, plan: QuestionPlan) -> None:
        if request.stamp != self._question_stamp():
            raise GameError("That model response belongs to an earlier move.")
        self._require_turn(player=True)
        if plan.statement_id is not None and plan.statement_id not in self._eligible_statements():
            raise GameError("That response is unavailable for this witness. Rephrase the question.")
        self._stage(Move(Kind.QUESTION, request.question, statement_id=plan.statement_id, grounds=plan.grounds))

    def _question_stamp(self) -> tuple[object, int, int]:
        return self._question_owner, self._turn_index, len(self.record)

    def offer_from_chat(self, message: str) -> bool:
        message = chat.bounded(message, chat.QUESTION_LIMIT)
        offer = re.fullmatch(r"(?:i\s+)?(?:offer|present|introduce|show)\s+(?:the\s+)?(.+)", message, re.I)
        if offer is None:
            return False
        query = words(offer[1])
        matches = [
            key for key in self.exhibits
            if query and (query == words(key) or mentions(words(self.case.exhibits[key].title), query))
        ]
        if len(matches) != 1:
            raise GameError("Use the title of one exhibit from the case file, such as “Offer the closing inventory.”")
        self.offer(matches[0])
        return True


    def advance_rival(self) -> None:
        while self.turn is not None and not self.player_turn and self.pending is None:
            self.rival_next()

    def offer(self, exhibit_id: str) -> None:
        turn = self._require_turn(player=True)
        if exhibit_id not in self.exhibits:
            raise GameError("Choose an exhibit available in this trial.")
        if exhibit_id in self._shown[turn.witness_id]:
            raise GameError("This witness has already been shown that exhibit.")
        exhibit = self.case.exhibits[exhibit_id]
        self._stage(Move(Kind.EXHIBIT, f"Offer {exhibit.title}.", exhibit_id=exhibit_id))

    def end_examination(self) -> None:
        self._require_turn(player=True)
        self._advance()

    def rival_next(self) -> None:
        turn = self._require_turn(player=False)
        while self._queue:
            script = self._queue.popleft()
            if script.exhibit_id is not None:
                if script.exhibit_id not in self._rival_exhibits or script.exhibit_id in self._shown[turn.witness_id]:
                    continue
                move = Move(Kind.EXHIBIT, script.text, exhibit_id=script.exhibit_id)
            else:
                statement_id = script.statement_id if script.statement_id in self._eligible_statements() else None
                move = Move(Kind.QUESTION, script.text, statement_id=statement_id, grounds=script.grounds)
            self._stage(move)
            return
        self._advance()

    def pass_rival_move(self) -> None:
        self._require_rival_review()
        self._accept()

    def object(self, ground: Ground, explanation: str = "") -> None:
        pending = self._require_rival_review()
        ground = Ground(ground)
        detail = f" {explanation.strip()}" if explanation.strip() else ""
        self._append("You", f"Objection. {ground.value}.{detail}", Status.SPOKEN)
        self.pending = replace(pending, objection=ground)
        self._resolve_objection("The rival asks to proceed with the move.", rival_reply=True)

    def reply(self, explanation: str = "") -> None:
        if not self.player_turn or self.pending is None or self.pending.objection is None:
            raise GameError("There is no rival objection to answer.")
        self._resolve_objection(explanation.strip(), rival_reply=False)

    def _eligible_statements(self) -> dict[str, Statement]:
        assert self.turn is not None
        witness_id = self.turn.witness_id
        return {
            key: statement for key, statement in self.case.witnesses[witness_id].statements.items()
            if self._shown[witness_id].issuperset(statement.requires_exhibits)
        }

    def _stage(self, move: Move, notice_only: bool = False) -> None:
        self.pending = Pending(move, notice_only=notice_only)
        if not self.player_turn:
            return
        ground = next((ground for ground in Ground if self._applies(ground, self.pending)), None)
        if ground is None:
            self._accept()
        else:
            self._append("Rival", f"Objection. {ground.value}.", Status.SPOKEN)
            self.pending = replace(self.pending, objection=ground)

    def _resolve_objection(self, explanation: str, rival_reply: bool) -> None:
        pending = self.pending
        assert pending is not None and pending.objection is not None
        ground = pending.objection
        move = pending.move
        if explanation:
            self._append("Rival" if rival_reply else "You", explanation, Status.SPOKEN)

        statement = self._eligible_statements().get(move.statement_id)
        for_notice = (
            ground == Ground.HEARSAY and statement is not None and statement.notice_purpose
            and mentions(words(explanation), "notice")
        )
        if for_notice:
            self._append("Judge", "Overruled. The statement may be considered for notice only.", Status.RULING)
            self.pending = replace(pending, notice_only=True)
            self._accept()
        elif self._applies(ground, pending):
            self._append("Judge", f"Sustained. {_GROUND_REASONS[ground]}", Status.RULING)
            status = Status.STRUCK if move.kind == Kind.ANSWER else Status.EXCLUDED
            speaker = self._witness_name() if move.kind == Kind.ANSWER else self._counsel()
            proof_id = move.statement_id if move.kind == Kind.ANSWER else move.exhibit_id
            self._append(speaker, move.text, status, proof_id)
            self.pending = None
        else:
            reason = (
                "A leading question is allowed on cross-examination."
                if ground == Ground.LEADING and self.turn.examination == Examination.CROSS
                else "That ground does not apply to this move."
            )
            self._append("Judge", f"Overruled. {reason}", Status.RULING)
            self._accept()

    def _applies(self, ground: Ground, pending: Pending) -> bool:
        assert self.turn is not None
        move = pending.move
        if ground == Ground.FOUNDATION:
            if move.exhibit_id is None:
                return False
            return (
                move.exhibit_id not in self.admitted_ids
                and not self.admitted_ids.issuperset(self.case.exhibits[move.exhibit_id].foundation)
            )
        if ground == Ground.LEADING:
            return self.turn.examination == Examination.DIRECT and ground in move.grounds
        if ground == Ground.HEARSAY and pending.notice_only:
            return False
        return ground in move.grounds

    def _accept(self) -> None:
        pending = self.pending
        turn = self.turn
        assert pending is not None and turn is not None
        self.pending = None
        move = pending.move
        if move.kind == Kind.EXHIBIT:
            assert move.exhibit_id is not None
            exhibit = self.case.exhibits[move.exhibit_id]
            status = Status.SHOWN if move.exhibit_id in self.admitted_ids else Status.ADMITTED
            self._shown[turn.witness_id].add(move.exhibit_id)
            self._append(self._counsel(), exhibit.title, status, move.exhibit_id, kind=Kind.EXHIBIT)
        elif move.kind == Kind.QUESTION:
            self._append(self._counsel(), move.text, Status.SPOKEN, kind=Kind.QUESTION)
            statement = self._eligible_statements().get(move.statement_id)
            text = statement.text if statement is not None else "Could you ask about something I personally observed?"
            if statement is not None and statement.delivery:
                text = f"{statement.delivery} {text}"
            grounds = (Ground.HEARSAY,) if statement is not None and statement.notice_purpose else ()
            self._stage(Move(Kind.ANSWER, text, statement_id=move.statement_id, grounds=grounds), pending.notice_only)
        else:
            status = Status.LIMITED if pending.notice_only else Status.ADMITTED
            self._append(self._witness_name(), move.text, status, move.statement_id, kind=Kind.ANSWER)

    def _prepare_turn(self) -> None:
        self._queue.clear()
        turn = self.turn
        if turn is None or self.player_turn:
            return
        witness = self.case.witnesses[turn.witness_id]
        if self._turn_index == self._departure_turn:
            self._queue.append(witness.departures[turn.examination])
        self._queue.extend(witness.scripts[turn.examination])

    def _advance(self) -> None:
        self._turn_index += 1
        self._prepare_turn()

    def _require_turn(self, player: bool) -> Turn:
        turn = self.turn
        if turn is None or self.player_turn != player:
            raise GameError("It is the other side's turn or the examination has ended.")
        if self.pending is not None:
            raise GameError("Resolve the pending move before continuing.")
        return turn

    def _require_rival_review(self) -> Pending:
        if self.player_turn or self.pending is None or self.pending.objection is not None:
            raise GameError("There is no rival move to review.")
        return self.pending

    def _counsel(self) -> str:
        return "You" if self.player_turn else "Rival"

    def _witness_name(self) -> str:
        assert self.turn is not None
        return self.case.witnesses[self.turn.witness_id].name

    def _append(
        self, speaker: str, text: str, status: Status, proof_id: str | None = None,
        *, kind: Kind | None = None,
    ) -> None:
        witness_id = self.turn.witness_id if self.turn else None
        self.record.append(RecordEntry(
            len(self.record) + 1, speaker, text, status, proof_id, witness_id, kind,
        ))
