import unittest
from dataclasses import replace

from shiny_objection.cases import Examination, Side, load_case
from shiny_objection.game import Game, GameError
from shiny_objection.outcome import deliberate, sentence
from shiny_objection.trial import RecordEntry, Status, Trial
from test_cases import CASE_PATH
from test_trial import pass_rival_examination, ready_game


def run_to_closing(trial: Trial, play=None):
    while trial.turn is not None:
        if trial.player_turn:
            if play is not None:
                play(trial)
            trial.end_examination()
        else:
            pass_rival_examination(trial)


class OutcomeTests(unittest.TestCase):
    def test_rival_can_convict_and_player_can_earn_mitigation(self):
        game = Game(load_case(CASE_PATH), seed=1)
        game.choose_side(Side.DEFENSE)
        for request in ("keys", "closing clock", "maintenance"):
            game.investigate(request)
        game.finish_investigation()
        game.choose_witnesses(("mira", "ivo"))
        trial = Trial(game)

        def show_leak(current):
            if current.turn.witness_id == "sen":
                current.offer("maintenance-log")

        run_to_closing(trial, show_leak)
        verdict = deliberate(trial, "The record shows the leak.")
        self.assertTrue(verdict.convicted)
        self.assertTrue(all(finding.evidence for finding in verdict.findings))
        self.assertEqual(len(verdict.sentencing.factors), 1)
        factor = verdict.sentencing.factors[0]
        self.assertIn("maintenance-log", {entry.proof_id for entry in factor.evidence})
        self.assertEqual(sentence(verdict, ()).duration, 8)
        self.assertEqual(sentence(verdict, (factor.label,)).duration, 5)

    def test_player_can_win_as_prosecutor_using_authored_proof(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))

        def prove_charge(current):
            if current.turn.examination != Examination.DIRECT:
                return
            if current.turn.witness_id == "lio":
                current.offer("closing-inventory")
                current.offer("recovery-note")
                current.ask("Who wrote the receipt?")
                current.offer("handoff-receipt")
                current.ask("What did you see at the handoff?")
                current.ask("When was the confirmed time?")
            else:
                current.ask("What did the transfer register show?")
                current.offer("transfer-register")

        run_to_closing(trial, prove_charge)
        admitted = next(entry.number for entry in trial.record if entry.proof_id == "handoff-receipt")
        verdict = deliberate(trial, "The handoff and transfer records prove the charge.", (admitted,))
        self.assertTrue(verdict.convicted)
        self.assertEqual(verdict.closing_citations[0].proof_id, "handoff-receipt")
        with self.assertRaises(GameError):
            sentence(verdict, ("unsupported mitigation",))

    def test_missing_struck_and_limited_proof_cannot_convict(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        with self.assertRaisesRegex(GameError, "Finish"):
            deliberate(trial, "The record is complete.")
        run_to_closing(trial)
        number = len(trial.record) + 1
        trial.record.extend([
            RecordEntry(number, "Witness", "Excluded claim", Status.STRUCK, "lio-handoff"),
            RecordEntry(number + 1, "Witness", "Limited claim", Status.LIMITED, "sen-register"),
        ])
        with self.assertRaisesRegex(GameError, "admitted"):
            deliberate(trial, "Use the struck answer.", (number,))
        verdict = deliberate(trial, "The record leaves doubt.")
        self.assertFalse(verdict.convicted)
        self.assertFalse(any(finding.proven for finding in verdict.findings))
        with self.assertRaisesRegex(GameError, "no sentence"):
            sentence(verdict, ())

    def test_complete_proof_alternative_wins_over_an_incomplete_one(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        element = replace(
            trial.case.elements[0],
            alternatives=(("closing-inventory", "recovery-note"), ("closing-inventory",)),
        )
        trial.case = replace(trial.case, elements=(element,))
        trial.offer("closing-inventory")
        run_to_closing(trial)
        self.assertTrue(deliberate(trial, "The inventory establishes the element.").convicted)
