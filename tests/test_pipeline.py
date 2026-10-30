"""End-to-end checks for task validation, inference, resume and scoring."""

import json
import tempfile
import unittest
from pathlib import Path

from datajevbench.core import CriticalInferenceError, read_json, run_evaluation, score_run, sha256, validate_response, verify_assets


def task(iid, expected, subset):
    return {"id": iid, "family": "policy", "state": "Read this whole state.",
            "question": {"type": "choice", "instructions": "Choose.",
                         "criteria": {"A": "first", "B": "second"}},
            "labels": ["A", "B"], "expected": expected, "split": "public", "group": None,
            "provenance": {"subset": subset}}


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        release = self.root / "releases" / "v0.5"
        release.mkdir(parents=True)
        self.dataset = self.root / "tasks.jsonl"
        self.inputs = self.root / "inputs.jsonl"
        tasks = [task("one", "A", "D1"), task("two", "B", "D2")]
        inputs = [{key: row[key] for key in ("id", "state", "question", "labels")} for row in tasks]
        for path, rows in ((self.dataset, tasks), (self.inputs, inputs)):
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        manifest = {"version": "0.5", "records": 2, "by_subset": {"D1": 1, "D2": 1},
                    "files": {"data-jevbench-v0.5.jsonl": {"sha256": sha256(self.dataset)},
                              "inputs.jsonl": {"sha256": sha256(self.inputs)},
                              "contract.py": {"sha256": self.assets_scorer_sha()}}}
        self.manifest = release / "manifest.json"
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        self.assets = verify_assets(self.dataset, self.inputs, self.manifest)
        self.identity = {"model_id": "toy", "model_revision": "r1", "backend": "toy-python",
                         "backend_revision": "r1", "engine": "test:Toy", "engine_options": {},
                         "settings": {"prompt": "toy"}}

    @staticmethod
    def assets_scorer_sha():
        from datajevbench.core import SCORER
        return sha256(SCORER)

    def tearDown(self):
        self.temp.cleanup()

    def test_gold_free_run_resume_score(self):
        seen = []
        attempts = {"two": 0}

        def engine(request):
            self.assertEqual(set(request), {"id", "state", "question", "labels"})
            seen.append(request["id"])
            if request["id"] == "two":
                attempts["two"] += 1
                if attempts["two"] == 1:
                    raise RuntimeError("temporary failure")
                return {"answer": "B", "probabilities": {"A": 0.2, "B": 0.8}}
            return {"answer": "A", "probabilities": {"A": 0.6, "B": 0.4}}

        run_dir = self.root / "run"
        first = run_evaluation(self.assets, run_dir, engine, self.identity)
        self.assertEqual(first["valid"], 1)
        score = score_run(self.assets, run_dir)
        self.assertTrue(score["complete"])
        self.assertEqual(score["overall"]["accuracy"], 0.5)
        self.assertIsNone(score["overall"]["ece"])
        second = run_evaluation(self.assets, run_dir, engine, self.identity, resume=True)
        self.assertEqual(second["valid"], 2)
        self.assertEqual(seen, ["one", "two", "two"])
        score = score_run(self.assets, run_dir)
        self.assertEqual(score["overall"]["accuracy"], 1.0)
        self.assertIsNotNone(score["overall"]["ece"])
        self.assertEqual(set(score["by_subset"]), {"D1", "D2"})

    def test_tampering_and_invalid_probabilities_rejected(self):
        request = self.assets["inputs"][0]
        with self.assertRaises(ValueError):
            validate_response(request, {"answer": "A", "probabilities": {"A": 1.0}})
        with self.assertRaises(ValueError):
            validate_response(request, {"answer": "A", "probabilities": {"A": 0.2, "B": 0.8}})
        original = self.inputs.read_text(encoding="utf-8")
        self.inputs.write_text(original.replace('"id": "one"', '"id": "changed"', 1), encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_assets(self.dataset, self.inputs, self.manifest)

    def test_probability_sum_tolerance_and_original_values(self):
        request = self.assets["inputs"][0]
        rounded = {"answer": "A", "probabilities": {"A": 0.600017, "B": 0.4}}
        prediction = validate_response(request, rounded)
        self.assertEqual(prediction["probabilities"], rounded["probabilities"])
        from datajevbench.contract_v05 import score_predictions
        direct = score_predictions([self.assets["tasks"][0]], [prediction])
        self.assertEqual(direct["correct"], 1)
        self.assertAlmostEqual(direct["brier"], (0.600017 - 1) ** 2 + 0.4 ** 2)
        run_dir = self.root / "rounded-run"
        run_evaluation(self.assets, run_dir, lambda _: rounded, self.identity, limit=1)
        score = score_run(self.assets, run_dir)
        self.assertEqual(score["release"], "0.5")
        self.assertEqual(score["overall"]["correct"], 1)
        for a in (0.6011, 0.59):
            invalid = {"answer": "A", "probabilities": {"A": a, "B": 0.4}}
            with self.assertRaises(ValueError):
                validate_response(request, invalid)
            with self.assertRaises(ValueError):
                score_predictions([self.assets["tasks"][0]], [{"id": request["id"], **invalid}])

    def test_scorer_hash_binds_score_and_resume(self):
        run_dir = self.root / "old-scorer"
        engine = lambda _: {"answer": "A"}
        run_evaluation(self.assets, run_dir, engine, self.identity)
        metadata = read_json(run_dir / "environment.json")
        metadata["scorer_sha256"] = "0" * 64
        (run_dir / "environment.json").write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "scorer_sha256"):
            score_run(self.assets, run_dir)
        with self.assertRaises(ValueError):
            run_evaluation(self.assets, run_dir, engine, self.identity, resume=True)

    def test_fatal_backend_error_stops_run(self):
        def engine(request):
            if request["id"] == "two":
                raise CriticalInferenceError("returned model changed")
            return {"answer": "A"}

        run_dir = self.root / "fatal-run"
        with self.assertRaises(CriticalInferenceError):
            run_evaluation(self.assets, run_dir, engine, self.identity)
        score = score_run(self.assets, run_dir)
        self.assertTrue(score["complete"])
        self.assertEqual(score["fatal_errors"], 1)

    def test_diagnostic_limit_is_preserved_on_resume(self):
        run_dir = self.root / "smoke"
        result = run_evaluation(self.assets, run_dir, lambda _: {"answer": "A"}, self.identity, limit=1)
        self.assertEqual(result["total"], 1)
        self.assertFalse(score_run(self.assets, run_dir)["complete"])
        with self.assertRaises(ValueError):
            run_evaluation(self.assets, run_dir, lambda _: {"answer": "A"}, self.identity, resume=True)


if __name__ == "__main__":
    unittest.main()
