import unittest

from shiny_objection.cases import Examination, Ground, Side, load_case
from shiny_objection.game import Game, GameError
from shiny_objection.models import QuestionPlan
from shiny_objection.trial import Kind, Status, Trial
from test_cases import CASE_PATH


_WITNESS_LEADS = {"mira": "keys", "ivo": "closing clock", "lio": "dry store", "sen": "permission"}


def ready_game(side: Side, witnesses: tuple[str, str], seed: int = 1) -> Game:
    game = Game(load_case(CASE_PATH), seed)
    game.choose_side(side)
    for witness in witnesses:
        game.investigate(_WITNESS_LEADS[witness])
    game.finish_investigation()
    game.choose_witnesses(witnesses)
    return game


def pass_rival_examination(trial: Trial) -> None:
    turn = trial.turn
    while trial.turn == turn:
        if trial.pending:
            trial.pass_rival_move()
        else:
            trial.rival_next()


class TrialTests(unittest.TestCase):
    def test_sustained_leading_question_never_reaches_witness(self):
        trial = Trial(ready_game(Side.DEFENSE, ("lio", "sen")))
        trial.rival_next()
        self.assertEqual(trial.turn.examination, Examination.DIRECT)
        self.assertIn("You saw Neri", trial.pending.move.text)
        with self.assertRaises(GameError):
            trial.rival_next()
        trial.object(Ground.LEADING)
        self.assertIsNone(trial.pending)
        self.assertTrue(any(entry.text.startswith("Sustained.") for entry in trial.record))
        self.assertEqual(trial.admitted_ids, frozenset())

    def test_leading_allowed_on_cross_answer_still_has_review(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        trial.end_examination()
        trial.rival_next()
        self.assertEqual(trial.turn.examination, Examination.CROSS)
        trial.object(Ground.LEADING)
        self.assertEqual(trial.pending.move.kind, Kind.ANSWER)
        self.assertEqual(trial.admitted_ids, frozenset())
        trial.pass_rival_move()
        self.assertIn("lio-unsure", trial.admitted_ids)
        self.assertTrue(any(entry.text.startswith("Overruled.") for entry in trial.record))

    def test_rival_objection_allows_player_reply_before_ruling(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        trial.ask("You saw Neri bring the ledger, didn't you?")
        self.assertEqual(trial.pending.objection, Ground.LEADING)
        self.assertFalse(any(entry.status == Status.RULING for entry in trial.record))
        with self.assertRaises(GameError):
            trial.end_examination()
        trial.reply("I withdraw the wording.")
        self.assertNotIn("lio-handoff", trial.admitted_ids)

    def test_foundation_and_showing_an_exhibit_can_unlock_a_statement(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        trial.offer("handoff-receipt")
        self.assertEqual(trial.pending.objection, Ground.FOUNDATION)
        trial.reply()
        self.assertNotIn("handoff-receipt", trial.admitted_ids)
        trial.ask("Who wrote the receipt?")
        trial.offer("handoff-receipt")
        trial.ask("When was the confirmed time?")
        self.assertTrue({"lio-receipt", "handoff-receipt", "lio-confirmed-time"} <= trial.admitted_ids)

    def test_no_offer_for_an_undisclosed_exhibit(self):
        trial = Trial(ready_game(Side.DEFENSE, ("lio", "ivo")))
        pass_rival_examination(trial)
        self.assertTrue(trial.player_turn)
        with self.assertRaisesRegex(GameError, "available"):
            trial.offer("maintenance-log")

    def test_limited_notice_is_not_admitted_for_truth(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("mira", "lio")))
        trial.ask("What were you told?")
        self.assertEqual(trial.pending.objection, Ground.HEARSAY)
        trial.reply("For notice. It explains why you did not call.")
        self.assertTrue(any(entry.status == Status.LIMITED for entry in trial.record))
        self.assertNotIn("mira-heard", trial.admitted_ids)

    def test_player_can_strike_a_rival_answer_after_passing_on_the_question(self):
        trial = Trial(ready_game(Side.DEFENSE, ("lio", "sen"), seed=0))
        pass_rival_examination(trial)
        trial.end_examination()
        trial.rival_next()
        self.assertEqual(trial.turn.witness_id, "mira")
        trial.pass_rival_move()
        self.assertEqual(trial.pending.move.kind, Kind.ANSWER)
        trial.object(Ground.HEARSAY)
        self.assertTrue(any(entry.status == Status.STRUCK for entry in trial.record))
        self.assertNotIn("mira-heard", trial.admitted_ids)

    def test_speculative_and_unrelated_questions_draw_distinct_grounds(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        trial.ask("Why do you think Neri moved the ledger?")
        self.assertEqual(trial.pending.objection, Ground.SPECULATION)
        trial.reply()
        trial.ask("Is music your favorite hobby?")
        self.assertEqual(trial.pending.objection, Ground.RELEVANCE)

    def test_snapshot_rejects_duplicate_and_other_trial_responses(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        other = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        request = trial.prepare_question("Who wrote the receipt?")
        plan = QuestionPlan("lio-receipt")
        with self.assertRaisesRegex(GameError, "earlier move"):
            other.apply_question(request, plan)
        trial.apply_question(request, plan)
        with self.assertRaisesRegex(GameError, "earlier move"):
            trial.apply_question(request, plan)
        self.assertEqual([entry.proof_id for entry in trial.record].count("lio-receipt"), 1)
        self.assertEqual(other.record, [])

    def test_model_context_carries_public_followup_but_excludes_locked_answer(self):
        trial = Trial(ready_game(Side.PROSECUTION, ("lio", "sen")))
        trial.ask("Who wrote the receipt?")
        request = trial.prepare_question("What time was that?")
        self.assertIn("You: Who wrote the receipt?", request.context)
        self.assertIn("watched Neri sign it", request.context[-1])
        self.assertNotIn("lio-confirmed-time", request.eligible)
        with self.assertRaisesRegex(GameError, "unavailable"):
            trial.apply_question(request, QuestionPlan("lio-confirmed-time"))
