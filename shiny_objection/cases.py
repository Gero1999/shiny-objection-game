"""Load the authored case data and check that its references can be played."""

import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType


class Side(StrEnum):
    PROSECUTION = "prosecution"
    DEFENSE = "defense"

    @property
    def other(self) -> "Side":
        return Side.DEFENSE if self == Side.PROSECUTION else Side.PROSECUTION


class Ground(StrEnum):
    LEADING = "Leading"
    HEARSAY = "Hearsay"
    SPECULATION = "Speculation"
    RELEVANCE = "Relevance"
    FOUNDATION = "Lack of foundation"


class Examination(StrEnum):
    DIRECT = "direct"
    CROSS = "cross"


@dataclass(frozen=True)
class Exhibit:
    title: str
    text: str
    foundation: tuple[str, ...]


@dataclass(frozen=True)
class Statement:
    text: str
    topics: tuple[str, ...]
    requires_exhibits: tuple[str, ...]
    notice_purpose: bool


@dataclass(frozen=True)
class ScriptedMove:
    text: str
    statement_id: str | None = None
    exhibit_id: str | None = None
    grounds: tuple[Ground, ...] = ()


@dataclass(frozen=True)
class Witness:
    name: str
    profile: str
    motive: str
    statements: Mapping[str, Statement]
    scripts: Mapping[Examination, tuple[ScriptedMove, ...]]
    departures: Mapping[Examination, ScriptedMove]


@dataclass(frozen=True)
class Lead:
    label: str
    aliases: tuple[str, ...]
    exhibits: tuple[str, ...]
    witnesses: tuple[str, ...]
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Element:
    label: str
    alternatives: tuple[tuple[str, ...], ...]
    contradictions: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class Mitigation:
    label: str
    requires: tuple[str, ...]
    reduction: int


@dataclass(frozen=True)
class Sentence:
    baseline: int
    minimum: int
    unit: str
    factors: tuple[Mitigation, ...]


@dataclass(frozen=True)
class CaseDefinition:
    id: str
    title: str
    jurisdiction: str
    charge: str
    briefing: str
    private_truth: str
    opening_exhibits: tuple[str, ...]
    lead_budget: int
    leads: Mapping[str, Lead]
    exhibits: Mapping[str, Exhibit]
    witnesses: Mapping[str, Witness]
    rival_witnesses: Mapping[Side, tuple[str, ...]]
    rival_exhibits: Mapping[Side, tuple[str, ...]]
    elements: tuple[Element, ...]
    sentence: Sentence


def _script(move: dict) -> ScriptedMove:
    return ScriptedMove(
        text=move["text"],
        statement_id=move.get("statement"),
        exhibit_id=move.get("exhibit"),
        grounds=tuple(Ground(ground) for ground in move.get("grounds", [])),
    )


def _parse(data: dict) -> CaseDefinition:
    exhibits = {
        key: Exhibit(item["title"], item["text"], tuple(item.get("foundation", [])))
        for key, item in data["exhibits"].items()
    }
    witnesses = {}
    for key, item in data["witnesses"].items():
        statements = {
            statement_id: Statement(
                statement["text"],
                tuple(statement["topics"]),
                tuple(statement.get("requires_exhibits", [])),
                statement.get("notice_purpose", False),
            )
            for statement_id, statement in item["statements"].items()
        }
        scripts = {
            exam: tuple(_script(move) for move in item["scripts"][exam])
            for exam in Examination
        }
        departures = {
            Examination(exam): _script(move)
            for exam, move in item.get("departures", {}).items()
        }
        witnesses[key] = Witness(
            item["name"], item["profile"], item["motive"],
            MappingProxyType(statements), MappingProxyType(scripts), MappingProxyType(departures),
        )

    leads = {
        key: Lead(
            item["label"], tuple(item["aliases"]), tuple(item["exhibits"]),
            tuple(item["witnesses"]), tuple(item.get("requires", [])),
        )
        for key, item in data["leads"].items()
    }
    elements = tuple(
        Element(
            item["label"],
            tuple(tuple(alternative) for alternative in item["alternatives"]),
            MappingProxyType({
                trigger: tuple(resolution)
                for trigger, resolution in item.get("contradictions", {}).items()
            }),
        )
        for item in data["elements"]
    )
    sentence = data["sentence"]
    return CaseDefinition(
        id=data["id"],
        title=data["title"],
        jurisdiction=data["jurisdiction"],
        charge=data["charge"],
        briefing=data["briefing"],
        private_truth=data["private_truth"],
        opening_exhibits=tuple(data["opening_exhibits"]),
        lead_budget=data["lead_budget"],
        leads=MappingProxyType(leads),
        exhibits=MappingProxyType(exhibits),
        witnesses=MappingProxyType(witnesses),
        rival_witnesses=MappingProxyType({
            side: tuple(data["rival"][side]["witnesses"]) for side in Side
        }),
        rival_exhibits=MappingProxyType({
            side: tuple(data["rival"][side]["exhibits"]) for side in Side
        }),
        elements=elements,
        sentence=Sentence(
            sentence["baseline"], sentence["minimum"], sentence["unit"],
            tuple(
                Mitigation(factor["label"], tuple(factor["requires"]), factor["reduction"])
                for factor in sentence["factors"]
            ),
        ),
    )


def _references(ids, expected, label: str) -> None:
    missing = set(ids).difference(expected)
    if missing:
        raise ValueError(f"{label} references unknown IDs: {', '.join(sorted(missing))}")


def _check_leads(case: CaseDefinition) -> None:
    for lead in case.leads.values():
        _references(lead.exhibits, case.exhibits, lead.label)
        _references(lead.witnesses, case.witnesses, lead.label)
        _references(lead.requires, case.leads, lead.label)
        if not lead.aliases or not all(lead.aliases):
            raise ValueError(f"{lead.label} needs investigation aliases")

    def walk(done: frozenset[str], discovered: frozenset[str]) -> None:
        available = [
            key for key, lead in case.leads.items()
            if key not in done and done.issuperset(lead.requires)
        ]
        if len(done) == case.lead_budget or not available:
            if len(discovered) < 2:
                raise ValueError("An investigation can finish with fewer than two witnesses")
            return
        for key in available:
            walk(done | {key}, discovered.union(case.leads[key].witnesses))

    if not 0 < case.lead_budget <= len(case.leads):
        raise ValueError("The investigation budget must fit the number of leads")
    walk(frozenset(), frozenset())


def _validate(case: CaseDefinition) -> None:
    if len(case.witnesses) < 4:
        raise ValueError("A case needs at least four witnesses")
    statement_ids = [key for witness in case.witnesses.values() for key in witness.statements]
    proof_ids = set(statement_ids).union(case.exhibits)
    if len(proof_ids) != len(statement_ids) + len(case.exhibits):
        raise ValueError("Statement and exhibit IDs must be unique")

    _references(case.opening_exhibits, case.exhibits, "Opening")
    for side in Side:
        lineup = case.rival_witnesses[side]
        if len(lineup) != len(case.witnesses) or set(lineup) != set(case.witnesses):
            raise ValueError(f"{side.value} needs an ordered list of all witnesses")
        _references(case.rival_exhibits[side], case.exhibits, side.value)
    for exhibit in case.exhibits.values():
        _references(exhibit.foundation, statement_ids, exhibit.title)
    for witness in case.witnesses.values():
        for statement in witness.statements.values():
            _references(statement.requires_exhibits, case.exhibits, witness.name)
        if any(not sequence for sequence in witness.scripts.values()):
            raise ValueError(f"{witness.name} needs a direct and cross script")
        for move in (*witness.scripts[Examination.DIRECT], *witness.scripts[Examination.CROSS],
                     *witness.departures.values()):
            if move.statement_id and move.exhibit_id:
                raise ValueError(f"An authored move by {witness.name} mixes a question and exhibit")
            if move.statement_id:
                _references((move.statement_id,), witness.statements, witness.name)
            if move.exhibit_id:
                _references((move.exhibit_id,), case.exhibits, witness.name)

    if not case.elements:
        raise ValueError("The charge needs at least one element")
    for element in case.elements:
        if not element.alternatives or not all(element.alternatives):
            raise ValueError(f"{element.label} needs nonempty proof alternatives")
        for alternative in element.alternatives:
            _references(alternative, proof_ids, element.label)
        for trigger, resolution in element.contradictions.items():
            _references((trigger, *resolution), proof_ids, element.label)
    if not 0 <= case.sentence.minimum <= case.sentence.baseline:
        raise ValueError("Invalid sentencing range")
    for factor in case.sentence.factors:
        if factor.reduction <= 0 or not factor.requires:
            raise ValueError(f"Invalid mitigation factor: {factor.label}")
        _references(factor.requires, proof_ids, factor.label)
    _check_leads(case)


def load_case(path: Path) -> CaseDefinition:
    """Read a version-one case and reject inconsistent references."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["version"] != 1:
            raise ValueError("Expected case format version 1")
        case = _parse(data)
        _validate(case)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError(f"{path.name}: {error}") from error
    return case


def select_case(cases: tuple[CaseDefinition, ...], seed: int) -> CaseDefinition:
    if not cases:
        raise ValueError("There are no authored cases")
    return random.Random(seed).choice(sorted(cases, key=lambda case: case.id))
