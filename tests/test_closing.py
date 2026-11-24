import unittest

from shiny_objection import chat
from shiny_objection.cases import Side
from shiny_objection.game import GameError
from shiny_objection.outcome import deliberate, rival_closing, verdict_summary
from shiny_objection.trial import Trial
from test_outcome import run_to_closing
from test_trial import ready_game


class ClosingTests(unittest.TestCase):
    def test_closings_are_bounded_and_verdict_names_the_missing_proof(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        run_to_closing(trial)
        rival = rival_closing(trial)
        self.assertIn("last shift", rival)
        self.assertLessEqual(len(rival), chat.CLOSING_LIMIT)
        with self.assertRaisesRegex(GameError, "480 characters"):
            deliberate(trial, "x" * (chat.CLOSING_LIMIT + 1))
        verdict = deliberate(trial, "There is no direct evidence.")
        self.assertIn("reasonable doubt", verdict_summary(verdict))
