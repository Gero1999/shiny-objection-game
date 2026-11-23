import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from shiny_objection.cases import Examination, Side, load_case, select_case


CASE_PATH = Path(__file__).resolve().parents[1] / "cases" / "annex-ledger.json"


class CaseTests(unittest.TestCase):
    def test_first_case_loads_with_scripts_for_both_sides(self):
        case = load_case(CASE_PATH)
        self.assertEqual(case.opening_exhibits, ("closing-inventory",))
        self.assertEqual(set(case.rival_witnesses), set(Side))
        self.assertTrue(all(witness.scripts[Examination.CROSS] for witness in case.witnesses.values()))
        self.assertEqual(case.sentence.baseline, 8)

    def test_seeded_selection_is_independent_of_source_order(self):
        case = load_case(CASE_PATH)
        other = replace(case, id="second-case")
        self.assertEqual(select_case((case, other), 6), select_case((other, case), 6))

    def test_missing_evidence_reference_is_rejected(self):
        data = json.loads(CASE_PATH.read_text())
        data["elements"][0]["alternatives"] = [["missing"]]
        with self.assertRaisesRegex(ValueError, "unknown IDs: missing"):
            self.load_modified(data)

    def test_investigation_path_cannot_strand_the_player(self):
        data = json.loads(CASE_PATH.read_text())
        for lead in data["leads"].values():
            lead["witnesses"] = ["mira"]
        with self.assertRaisesRegex(ValueError, "fewer than two witnesses"):
            self.load_modified(data)

    def load_modified(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_case(path)
