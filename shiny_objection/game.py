"""Investigation and witness selection for a single playthrough."""

import re
from dataclasses import dataclass
from enum import StrEnum

from . import chat
from .cases import CaseDefinition, Side
from .errors import GameError as GameError


class Phase(StrEnum):
    BRIEFING = "briefing"
    CONSULTATION = "consultation"
    INVESTIGATION = "investigation"
    WITNESS_SELECTION = "witness selection"
    TRIAL = "trial"


@dataclass(frozen=True)
class ExhibitView:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class WitnessView:
    id: str
    name: str
    profile: str


@dataclass(frozen=True)
class PlayerView:
    title: str
    jurisdiction: str
    charge: str
    briefing: str
    phase: Phase
    side: Side | None
    investigations_left: int
    exhibits: tuple[ExhibitView, ...]
    witnesses: tuple[WitnessView, ...]
    player_lineup: tuple[str, ...]
    rival_lineup: tuple[str, ...]


def words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def mentions(normalized: str, phrase: str) -> bool:
    return f" {words(phrase)} " in f" {normalized} "


class Game:
    def __init__(self, case: CaseDefinition, seed: int):
        self.case = case
        self.seed = seed
        self.phase = Phase.BRIEFING
        self.side: Side | None = None
        self.completed_leads: set[str] = set()
        self.discovered_exhibits = set(case.opening_exhibits)
        self.discovered_witnesses: set[str] = set()
        self.interview: list[tuple[str, str]] = []
        self.player_lineup: tuple[str, ...] = ()
        self.rival_lineup: tuple[str, ...] = ()
        self.lead_chat: list[tuple[str, str]] = []

    @property
    def investigations_left(self) -> int:
        return self.case.lead_budget - len(self.completed_leads)

    def finish_consultation(self) -> None:
        self._require_phase(Phase.CONSULTATION)
        self.phase = Phase.INVESTIGATION


    def interview_client(self, question: str, statement_id: str | None) -> None:
        self._require_phase(Phase.CONSULTATION)
        question = chat.bounded(question, chat.QUESTION_LIMIT)
        statement = self.case.client.statements.get(statement_id)
        if statement_id is not None and statement is None:
            raise GameError("The client response was unavailable. Try asking again.")
        reply = statement.text if statement else "Ask me what happened or where you might look."
        self.interview.append((question, reply))

    def choose_side(self, side: Side) -> None:
        self._require_phase(Phase.BRIEFING)
        self.side = Side(side)
        self.phase = Phase.CONSULTATION if side == Side.DEFENSE else Phase.INVESTIGATION


    def available_leads(self) -> dict:
        self._require_phase(Phase.INVESTIGATION)
        if self.investigations_left == 0:
            raise GameError("You have used your investigation slots. Choose your witnesses.")
        return {key: lead for key, lead in self.case.leads.items()
                if self.completed_leads.issuperset(lead.requires)}


    def investigate(self, request: str) -> str:
        request = chat.bounded(request, chat.LEAD_LIMIT)
        query = words(request)
        matched = [
            key for key, lead in self.available_leads().items()
            if any(mentions(query, alias) for alias in lead.aliases)
        ]
        if not matched:
            raise GameError("Try a specific place, object, or person from the case briefing.")
        if len(matched) > 1:
            raise GameError("That could be more than one lead. Investigate one at a time.")
        return self.reveal_lead(request, matched[0])


    def reveal_lead(self, request: str, key: str | None) -> str:
        request = chat.bounded(request, chat.LEAD_LIMIT)
        lead = self.available_leads().get(key)
        if lead is None:
            raise GameError("Try a specific place, object, or person from the case briefing.")
        if key in self.completed_leads:
            raise GameError("You have already investigated that lead.")
        self.completed_leads.add(key)
        self.discovered_exhibits.update(lead.exhibits)
        self.discovered_witnesses.update(lead.witnesses)
        discoveries = [
            f"{item.title}. {item.text}" for item in (self.case.exhibits[id_] for id_ in lead.exhibits)
        ] + [
            f"{item.name}. {item.profile}" for item in (self.case.witnesses[id_] for id_ in lead.witnesses)
        ]
        self.lead_chat.append((request, " ".join(discoveries) or lead.label))
        return lead.label

    def finish_investigation(self) -> None:
        self._require_phase(Phase.INVESTIGATION)
        if len(self.discovered_witnesses) < 2:
            raise GameError("Discover at least two witnesses before ending the investigation.")
        self.phase = Phase.WITNESS_SELECTION

    def choose_witnesses(self, witness_ids: tuple[str, ...]) -> None:
        self._require_phase(Phase.WITNESS_SELECTION)
        if len(witness_ids) != 2 or len(set(witness_ids)) != 2:
            raise GameError("Choose two different witnesses.")
        if not self.discovered_witnesses.issuperset(witness_ids):
            raise GameError("Choose witnesses discovered during your investigation.")
        assert self.side is not None
        self.player_lineup = tuple(witness_ids)
        self.rival_lineup = tuple(
            key for key in self.case.rival_witnesses[self.side.other] if key not in witness_ids
        )[:2]
        self.phase = Phase.TRIAL

    def trial_exhibits(self) -> frozenset[str]:
        self._require_phase(Phase.TRIAL)
        assert self.side is not None
        return frozenset(self.discovered_exhibits.union(self.case.rival_exhibits[self.side.other]))

    def view(self) -> PlayerView:
        exhibits = self.discovered_exhibits
        witnesses = self.discovered_witnesses
        if self.phase == Phase.TRIAL:
            exhibits = self.trial_exhibits()
            witnesses = witnesses.union(self.rival_lineup)
        return PlayerView(
            title=self.case.title,
            jurisdiction=self.case.jurisdiction,
            charge=self.case.charge,
            briefing=self.case.briefing,
            phase=self.phase,
            side=self.side,
            investigations_left=self.investigations_left,
            exhibits=tuple(
                ExhibitView(key, exhibit.title, exhibit.text)
                for key, exhibit in self.case.exhibits.items() if key in exhibits
            ),
            witnesses=tuple(
                WitnessView(key, witness.name, witness.profile)
                for key, witness in self.case.witnesses.items() if key in witnesses
            ),
            player_lineup=self.player_lineup,
            rival_lineup=self.rival_lineup,
        )

    def _require_phase(self, phase: Phase) -> None:
        if self.phase != phase:
            raise GameError(f"That action belongs to the {phase.value} phase.")
