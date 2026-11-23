import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shiny_objection.cases import Ground, Lead, Statement
from shiny_objection.models import ModelError, verify_connection
from shiny_objection.ollama import OllamaDialogue


class TestOllamaHTTP(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.response = {"message": {"content": '{"statement_id":"clock","grounds":["Leading"]}'}}
        self.status = 200
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                test.requests.append((self.path, json.loads(body)))
                self.send_response(test.status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(test.response).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02})
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.dialogue = OllamaDialogue("smollm2:135m", f"http://127.0.0.1:{server.server_port}")

    def test_real_http_request_uses_enum_of_eligible_statements(self):
        eligible = {"clock": Statement("I saw the clock at seven.", ("clock",), (), False)}
        plan = self.dialogue.interpret("It was seven, correct?", eligible, ("You: Where were you?",))
        self.assertEqual(plan.statement_id, "clock")
        self.assertEqual(plan.grounds, (Ground.LEADING,))
        path, request = self.requests[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(request["model"], "smollm2:135m")
        self.assertEqual(request["format"]["properties"]["statement_id"]["enum"], [None, "clock"])
        self.assertFalse(request["stream"])
        user_message = json.loads(request["messages"][1]["content"])
        self.assertEqual(user_message["recent_exchange"], ["You: Where were you?"])

    def test_rejects_unauthorized_statement_and_invalid_shape(self):
        for decoded in (
            {"statement_id": "sealed", "grounds": []},
            {"statement_id": "clock", "grounds": ["Lack of foundation"]},
            {"statement_id": "clock", "grounds": "Leading"},
            {"statement_id": "clock", "grounds": [], "testimony": "Invented fact"},
        ):
            with self.subTest(decoded=decoded):
                self.response["message"]["content"] = json.dumps(decoded)
                with self.assertRaisesRegex(ModelError, "invalid witness plan"):
                    verify_connection(self.dialogue)

    def test_http_error_displays_only_status(self):
        self.status = 403
        self.response = {"error": "raw service data"}
        with self.assertRaisesRegex(ModelError, "HTTP 403") as raised:
            verify_connection(self.dialogue)
        self.assertNotIn("raw service data", str(raised.exception))

    def test_rejects_credentials_in_endpoint(self):
        with self.assertRaisesRegex(ModelError, "endpoint is invalid"):
            OllamaDialogue("smollm2:135m", "http://secret@localhost:11434")

    def test_model_can_select_a_lead_without_receiving_its_unlocked_material(self):
        leads = {"key-cabinet": Lead("Key cabinet", ("key",), ("private-log",), ("mira",), ())}
        self.response["message"]["content"] = '{"lead_id":"key-cabinet"}'
        self.assertEqual(self.dialogue.find_lead("Check whose key fit the lock", leads), "key-cabinet")
        message = self.requests[0][1]["messages"][1]["content"]
        self.assertNotIn("private-log", message)
        self.assertNotIn("mira", message)

        self.response["message"]["content"] = '{"lead_id":"invented"}'
        with self.assertRaisesRegex(ModelError, "invalid investigation result"):
            self.dialogue.find_lead("Find the answer", leads)
