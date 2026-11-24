import unittest

from shiny_objection.cases import Side, load_case
from shiny_objection.game import Game
from shiny_objection.outcome import deliberate, sentence
from shiny_objection.trial import Trial
from test_cases import CASE_PATH
from test_outcome import run_to_closing


class HonestBellTests(unittest.TestCase):
    def start_trial(self, side, witness, leads):
        game = Game(load_case(CASE_PATH.with_name("honest-bell.json")), seed=1)
        game.choose_side(side)
        if side == Side.DEFENSE:
            game.finish_consultation()
        for lead in leads:
            game.investigate(lead)
        game.finish_investigation()
        game.choose_witnesses((witness,))
        return Trial(game)

    def test_prosecution_can_resolve_the_conflicting_handoff(self):
        trial = self.start_trial(Side.PROSECUTION, "fig", ("stage", "print shop", "bun stall"))
        trial.offer("patrol-note")
        trial.offer("confession-sign")
        trial.offer("bank-receipt")
        trial.ask("Who initialed the cue card?")
        trial.offer("cue-card")
        trial.offer("rehearsal-book")
        trial.ask("What do the two copies show?")
        run_to_closing(trial)

        self.assertIn("bun-late", trial.admitted_ids)
        self.assertIn("fig-two-copies", trial.admitted_ids)
        self.assertTrue(deliberate(trial, "The cue changed hands twice.").convicted)

    def test_defense_can_leave_reasonable_doubt_about_the_first_handoff(self):
        trial = self.start_trial(Side.DEFENSE, "bun", ("bun stall", "cash office"))

        def question_bun(current):
            if current.turn.witness_id == "bun":
                current.ask("When was the card handed over at your counter?")

        run_to_closing(trial, question_bun)
        verdict = deliberate(trial, "The record gives different times for the handoff.")
        self.assertFalse(verdict.convicted)
        self.assertEqual([entry.proof_id for entry in verdict.findings[-1].unresolved], ["bun-late"])

    def test_defense_can_reduce_the_sentence_with_a_documented_correction(self):
        trial = self.start_trial(Side.DEFENSE, "dot", ("cash office", "print shop"))

        def show_correction(current):
            if current.turn.witness_id == "dot":
                current.ask("Who posted the correction slip?")
                current.offer("correction-slip")

        run_to_closing(trial, show_correction)
        verdict = deliberate(trial, "Pip corrected the accusation before police arrived.")
        self.assertTrue(verdict.convicted)
        factor, = verdict.sentencing.factors
        self.assertEqual(sentence(verdict, (factor.label,)).duration, 3)
