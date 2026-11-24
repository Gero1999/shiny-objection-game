import unittest
from dataclasses import asdict

from shiny_objection.cases import Side, load_case
from shiny_objection.game import Game, GameError, Phase
from test_cases import CASE_PATH


class GameTests(unittest.TestCase):
    def setUp(self):
        self.case = load_case(CASE_PATH)
        self.game = Game(self.case, seed=2)

    def test_briefing_has_no_private_facts_or_witnesses(self):
        view = self.game.view()
        self.assertEqual([exhibit.id for exhibit in view.exhibits], ["closing-inventory"])
        self.assertEqual(view.witnesses, ())
        self.assertNotIn("private_truth", asdict(view))
        self.assertNotIn(self.case.private_truth, repr(view))

    def test_failed_and_duplicate_leads_do_not_spend_budget(self):
        self.game.choose_side(Side.DEFENSE)
        self.game.finish_consultation()
        for request in ("", "Explain every secret", "Check the key cabinet and dry store"):
            with self.assertRaises(GameError):
                self.game.investigate(request)
        self.assertEqual(self.game.investigations_left, 3)
        self.game.investigate("Who used the key cabinet?")
        with self.assertRaises(GameError):
            self.game.investigate("Search the keys again")
        self.assertEqual(self.game.investigations_left, 2)
        self.assertEqual([witness.id for witness in self.game.view().witnesses], ["mira"])
        self.assertNotIn(self.case.witnesses["mira"].motive, repr(self.game.view()))

    def test_lineups_are_distinct_and_disclosures_wait_until_trial(self):
        self.game.choose_side(Side.PROSECUTION)
        for request in ("Check storage", "Ask the supervisor"):
            self.game.investigate(request)
        self.game.finish_investigation()
        with self.assertRaises(GameError):
            self.game.choose_witnesses(("mira", "lio"))
        self.assertEqual(self.game.phase, Phase.WITNESS_SELECTION)
        self.assertNotIn("key-register", {item.id for item in self.game.view().exhibits})
        self.game.choose_witnesses(("lio", "sen"))
        view = self.game.view()
        self.assertEqual(view.player_lineup, ("lio", "sen"))
        self.assertEqual(view.rival_lineup, ("mira", "ivo"))
        self.assertIn("key-register", {item.id for item in view.exhibits})

    def test_sessions_do_not_share_discoveries(self):
        another = Game(self.case, seed=2)
        self.game.choose_side(Side.DEFENSE)
        self.game.finish_consultation()
        self.game.investigate("Check the closing clock")
        self.assertEqual([exhibit.id for exhibit in another.view().exhibits], ["closing-inventory"])
        self.assertEqual(another.phase, Phase.BRIEFING)

    def test_defense_can_interview_client_before_investigation(self):
        self.game.choose_side(Side.DEFENSE)
        self.assertEqual(self.game.phase, Phase.CONSULTATION)
        with self.assertRaises(GameError):
            self.game.investigate("dry store")
        self.game.interview_client("Where did you take the ledger?", "client-move")
        self.assertIn("dry store", self.game.interview[-1][1])
        self.assertEqual(self.game.discovered_exhibits, {"closing-inventory"})
