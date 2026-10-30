"""Protect public IDs, inference boundaries and frozen source/public identity."""

import copy
import json
from pathlib import Path
import unittest

from datajevbench.contract_v05 import model_input, score_predictions
from datajevbench.core import verify_assets
from datajevbench.engines import SystemOneHTTP
from datajevbench.publication import (FORMAT, public_id, public_record, semantic_digest,
                                      validate_publication, wire_digest)


ROOT = Path(__file__).resolve().parents[1]


def example():
    return {"id": "private-construction-batch", "family": "policy", "state": "Retain valid records.",
            "question": {"type": "choice", "instructions": "Choose.",
                         "criteria": {"KEEP": "keep", "DROP": "drop"}},
            "labels": ["KEEP", "DROP"], "expected": "KEEP", "split": "public", "group": "source-family",
            "provenance": {"subset": "D1", "source": "authored", "source_url": None, "license": "fixture",
                           "source_sha256": None, "operator_document_sha256": None,
                           "reference_type": "rule_or_source_supported", "language": {"task_language": "en"},
                           "measured_difficulty": {"panel_accuracy": 1.0}, "summary": "Answer is KEEP"}}


class DataPublicationTest(unittest.TestCase):
    def test_id_excludes_gold_and_provenance_but_binds_visible_content(self):
        task = example()
        original = public_id(task)
        changed = copy.deepcopy(task)
        changed["id"] = "another-construction-batch"
        changed["expected"] = "DROP"
        changed["provenance"]["summary"] = "Answer is DROP"
        changed["provenance"]["measured_difficulty"] = {"panel_accuracy": 0.0}
        self.assertEqual(public_id(changed), original)
        changed["state"] += " New rule."
        self.assertNotEqual(public_id(changed), original)
        reordered = copy.deepcopy(task)
        reordered["labels"].reverse()
        self.assertNotEqual(public_id(reordered), original)

    def test_projection_keeps_wire_order_references_and_scoring(self):
        original = example()
        published = public_record(original)
        self.assertEqual(list(published["question"]["criteria"]), ["KEEP", "DROP"])
        self.assertNotIn("summary", published["provenance"])
        self.assertNotIn("measured_difficulty", published["provenance"])
        self.assertNotIn(original["id"], json.dumps(published))
        old_input, new_input = model_input(original), model_input(published)
        self.assertEqual(SystemOneHTTP.wire_payload(old_input, "test"),
                         SystemOneHTTP.wire_payload(new_input, "test"))
        prediction = {"id": original["id"], "answer": "KEEP", "probabilities": {"KEEP": .7, "DROP": .3}}
        renamed = {**prediction, "id": published["id"]}
        self.assertEqual(score_predictions([original], [prediction]),
                         score_predictions([published], [renamed]))
        self.assertEqual(semantic_digest([original]), semantic_digest([published]))
        metadata = {"format": FORMAT, "semantic_sha256": semantic_digest([original]),
                    "model_wire_sha256": wire_digest([old_input])}
        validate_publication([published], [new_input], metadata)
        leaked = copy.deepcopy(published)
        leaked["provenance"]["summary"] = "Answer is KEEP"
        with self.assertRaisesRegex(ValueError, "provenance"):
            validate_publication([leaked], [new_input], metadata)

    def test_published_data_is_complete_and_projection_has_no_gold(self):
        assets = verify_assets(ROOT / "benchmark/records.jsonl", ROOT / "benchmark/inputs.jsonl")
        self.assertEqual(len(assets["tasks"]), 500)
        self.assertEqual(len({task["id"] for task in assets["tasks"]}), 500)
        for row in assets["inputs"]:
            self.assertRegex(row["id"], r"^D[1-6]-[0-9a-f]{16}$")
            self.assertEqual(set(row), {"id", "state", "question", "labels"})
            wire = SystemOneHTTP.wire_payload(row, "test")
            self.assertEqual(set(wire), {"model", "state", "questions"})
        original_manifest = json.loads((ROOT / "releases/v0.5/source-manifest.json").read_text())
        self.assertEqual(assets["manifest"]["source_files"], original_manifest["files"])

    def test_historical_board_does_not_acquire_public_run_hashes(self):
        board = json.loads((ROOT / "results/leaderboard.json").read_text())
        manifest = json.loads((ROOT / "releases/v0.5/manifest.json").read_text())
        self.assertEqual(board["dataset_sha256"], manifest["source_files"]["data-jevbench-v0.5.jsonl"]["sha256"])
        self.assertNotEqual(board["dataset_sha256"], manifest["files"]["data-jevbench-v0.5.jsonl"]["sha256"])


if __name__ == "__main__":
    unittest.main()
