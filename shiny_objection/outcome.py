"""Evaluate the fictional charge and sentence from the admitted trial record."""

from dataclasses import dataclass

from .game import GameError
from .trial import RecordEntry, Status, Trial


@dataclass(frozen=True)
class Finding:
    element: str
    proven: bool
    evidence: tuple[RecordEntry, ...]
    unresolved: tuple[RecordEntry, ...]


@dataclass(frozen=True)
class SupportedMitigation:
    label: str
    reduction: int
    evidence: tuple[RecordEntry, ...]


@dataclass(frozen=True)
class SentencingOptions:
    baseline: int
    minimum: int
    unit: str
    factors: tuple[SupportedMitigation, ...]


@dataclass(frozen=True)
class Verdict:
    findings: tuple[Finding, ...]
    closing_argument: str
    closing_citations: tuple[RecordEntry, ...]
    sentencing: SentencingOptions | None

    @property
    def convicted(self) -> bool:
        return self.sentencing is not None


@dataclass(frozen=True)
class SentenceResult:
    baseline: int
    duration: int
    unit: str
    factors: tuple[SupportedMitigation, ...]


def deliberate(trial: Trial, argument: str, citations: tuple[int, ...] = ()) -> Verdict:
    if trial.turn is not None or trial.pending is not None:
        raise GameError("Finish the examinations before presenting a closing argument.")
    if not argument.strip():
        raise GameError("Write a short closing argument.")

    admitted = {
        entry.number: entry for entry in trial.record
        if entry.status == Status.ADMITTED and entry.proof_id is not None
    }
    if not admitted.keys() >= set(citations):
        raise GameError("Cite only admitted proof from the record.")
    proof = {}
    for entry in admitted.values():
        proof.setdefault(entry.proof_id, entry)

    findings = []
    for element in trial.case.elements:
        best = max(
            element.alternatives,
            key=lambda ids: (proof.keys() >= set(ids), sum(key in proof for key in ids)),
        )
        evidence = tuple(proof[key] for key in best if key in proof)
        unresolved = tuple(
            proof[trigger] for trigger, resolution in element.contradictions.items()
            if trigger in proof and not proof.keys() >= set(resolution)
        )
        findings.append(Finding(element.label, len(evidence) == len(best) and not unresolved, evidence, unresolved))

    sentencing = None
    if all(finding.proven for finding in findings):
        rule = trial.case.sentence
        sentencing = SentencingOptions(
            rule.baseline, rule.minimum, rule.unit,
            tuple(
                SupportedMitigation(factor.label, factor.reduction, tuple(proof[key] for key in factor.requires))
                for factor in rule.factors if proof.keys() >= set(factor.requires)
            ),
        )
    return Verdict(tuple(findings), argument.strip(), tuple(admitted[key] for key in dict.fromkeys(citations)), sentencing)


def sentence(verdict: Verdict, requested: tuple[str, ...]) -> SentenceResult:
    options = verdict.sentencing
    if options is None:
        raise GameError("An acquittal has no sentence.")
    factors = {factor.label: factor for factor in options.factors}
    if not factors.keys() >= set(requested):
        raise GameError("Select mitigation supported by the admitted record.")
    applied = tuple(factors[key] for key in dict.fromkeys(requested))
    duration = max(options.minimum, options.baseline - sum(factor.reduction for factor in applied))
    return SentenceResult(options.baseline, duration, options.unit, applied)
