import unittest

from shiny_objection.cases import Side, load_case
from shiny_objection.game import Game, GameError
from test_cases import CASE_PATH


class InvestigationChatTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_case(CASE_PATH), seed=2)

    def test_a_long_input_and_unknown_model_lead_do_not_reveal_evidence(self):
        self.game.choose_side(Side.PROSECUTION)
        with self.assertRaises(GameError):
            self.game.investigate("keys " * 100)
        with self.assertRaises(GameError):
            self.game.reveal_lead("Please investigate", "invented")
        self.assertEqual(self.game.investigations_left, 3)
        self.game.reveal_lead("Who signed out a key?", "key-cabinet")
        self.assertIn("Spare key register", self.game.lead_chat[0][1])
        self.assertIn("Mira Senn", self.game.lead_chat[0][1])
        self.assertNotIn("dry store", self.game.lead_chat[0][1])
