import json
import unittest
from unittest.mock import patch

from shiny_objection.cases import Statement
from shiny_objection.hosted_model import OpenAIDialogue
from shiny_objection.models import ModelError


class OpenAIAdapterTests(unittest.TestCase):
    def test_responses_request_uses_token_only_in_header(self):
        token = "test-token"
        eligible = {"clock": Statement("I saw the clock at seven.", ("clock",), (), False)}
        response = {
            "status": "completed",
            "output": [
                {"type": "reasoning"},
                {"type": "message", "content": [
                    {"type": "output_text", "text": '{"statement_id":"clock","grounds":[]}'}
                ]},
            ],
        }
        with patch("shiny_objection.hosted_model.post_json", return_value=response) as request:
            plan = OpenAIDialogue(token, "gpt-4.1-mini").interpret("What time was it?", eligible)
        self.assertEqual(plan.statement_id, "clock")
        url, payload = request.call_args.args
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.call_args.kwargs["headers"], {"Authorization": "Bearer " + token})
        self.assertNotIn(token, json.dumps(payload))
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["schema"]["required"], ["statement_id", "grounds"])

    def test_incomplete_or_refused_responses_stop_before_game_action(self):
        for response in (
            {"status": "incomplete"},
            {"status": "completed", "output": [
                {"type": "message", "content": [{"type": "refusal", "refusal": "Service text"}]}
            ]},
        ):
            with self.subTest(response=response), patch(
                "shiny_objection.hosted_model.post_json", return_value=response
            ):
                with self.assertRaisesRegex(ModelError, "complete witness plan") as raised:
                    OpenAIDialogue("test-token", "gpt-4.1-mini").interpret("What time was it?", {})
                self.assertNotIn("Service text", str(raised.exception))

    def test_empty_or_malformed_token_is_rejected_before_a_request(self):
        for token in ("", " " * 3, "one\r\ntwo"):
            with self.subTest(token=token), self.assertRaisesRegex(ModelError, "API token"):
                OpenAIDialogue(token, "gpt-4.1-mini")
