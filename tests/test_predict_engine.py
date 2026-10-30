"""Validate the boundary with model-owned typed Choice/Score implementations."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from datajevbench.cli import main
from datajevbench.core import CriticalInferenceError, read_jsonl, run_evaluation, score_run
from datajevbench.engines import normalize_answers, SystemOneHTTP
from datajevbench.predict import create_predict


def request(kind="choice"):
    labels = ["Z", "A"] if kind == "choice" else ["0", "1", "2"]
    return {"id": "local-only", "state": {"text": "original state"}, "labels": labels,
            "question": {"type": kind, "instructions": {"rule": "Choose."},
                         "criteria": dict.fromkeys(labels, "option") if kind == "choice"
                         else ["low", "medium", "high"]}}


class Model:
    def predict(self, state, questions):
        self.received = deepcopy((state, questions))
        state.clear()
        questions["decision"]["instructions"] = "backend mutation"
        return {"answers": {"decision": {"type": "choice", "choice": "Z",
                                         "probabilities": {"Z": 0.5, "A": 0.5}}},
                "metadata": {"backend_note": "retained"}}


def assets():
    row = request()
    return {"inputs": [row], "tasks": [{**row, "expected": "A", "provenance": {"subset": "D1"}}],
            "manifest": {"by_subset": {"D1": 1}}, "dataset_sha256": "data",
            "inputs_sha256": "inputs", "scorer_sha256": "scorer"}


class PredictTest(unittest.TestCase):
    def make_engine(self, **kwargs):
        return create_predict(factory=f"{__name__}:Model", **kwargs)

    def test_projection_tie_break_and_raw_response(self):
        row = request()
        original = deepcopy(row)
        engine = self.make_engine()
        result = engine(row)
        self.assertEqual(row, original)
        self.assertEqual(engine.backend.received, (row["state"], {"decision": row["question"]}))
        self.assertEqual(result["answer"], "A")
        self.assertEqual(result["probabilities"], {"Z": 0.5, "A": 0.5})
        self.assertEqual(result["_predict_response"]["answers"]["decision"]["choice"], "Z")
        self.assertEqual(result["_predict_response"]["metadata"], {"backend_note": "retained"})

    def test_score_uses_argmax_not_expectation_on_both_paths(self):
        row = request("score")
        body = {"model": "toy", "answers": {"decision": {"type": "score", "score": 1.3,
                                                       "probabilities": {"0": 0.1, "1": 0.5, "2": 0.4}}}}
        result = normalize_answers(body, row)
        self.assertEqual(result["answer"], "1")
        self.assertEqual(result["probabilities"], body["answers"]["decision"]["probabilities"])
        self.assertEqual(SystemOneHTTP.normalize_response(body, row)["answer"], "1")
        del body["answers"]["decision"]["probabilities"]
        body["answers"]["decision"]["score"] = 1
        with self.assertRaisesRegex(ValueError, "expectation is not a label"):
            normalize_answers(body, row)

    def test_invalid_outputs_are_rejected_without_repair(self):
        for answer in [
            {"probabilities": {"Z": 0.2, "A": 0.2}},
            {"probabilities": {"Z": True, "A": 0}},
            {"probabilities": {"Z": float("nan"), "A": 0.5}},
            {"probabilities": {"Z": 1.1, "A": -0.1}},
            {"probabilities": {"Z": 1.0}},
            {"type": "score", "probabilities": {"Z": 0.5, "A": 0.5}},
            {"answer": "Z", "probabilities": {"Z": 0.2, "A": 0.8}},
        ]:
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                normalize_answers({"answers": {"decision": answer}}, request())
        result = normalize_answers({"answers": {"decision": {
            "probabilities": {"Z": 0.5002, "A": 0.5002}}}}, request())
        self.assertEqual(result["probabilities"], {"Z": 0.5002, "A": 0.5002})
        with self.assertRaises(ValueError):
            normalize_answers({"answers": {"decision": {"choice": "A"}, "extra": {}}}, request())

    def test_prediction_replays_without_loading_external_model(self):
        identity = {"engine": "datajevbench.predict:create_predict"}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            run_evaluation(assets(), out, self.make_engine(), identity)
            with patch("importlib.import_module", side_effect=AssertionError("No model imports")):
                self.assertEqual(score_run(assets(), out)["overall"]["accuracy"], 1.0)
            log = out / "results.jsonl"
            event = read_jsonl(log)[0]
            event["raw_output"]["answer"] = "Z"
            event["raw_output"]["probabilities"] = {"Z": 0.9, "A": 0.1}
            event["prediction"].update(answer="Z", probabilities={"Z": 0.9, "A": 0.1})
            log.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "Predict normalization differs"):
                score_run(assets(), out)

    def test_cli_fingerprints_external_sources_and_refuses_changed_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / "compiler.py"
            helper.write_text("revision = 1\n")
            options = root / "options.json"
            options.write_text(json.dumps({"factory": f"{__name__}:Model", "source_files": [str(helper)]}))
            settings = root / "settings.json"
            settings.write_text(json.dumps(dict.fromkeys(
                ["inference_method", "input_format", "hardware", "retry_policy"], "synthetic")))
            argv = ["run", "--engine", "datajevbench.predict:create_predict", "--engine-options", str(options),
                    "--dataset", str(settings), "--inputs", str(settings), "--settings", str(settings),
                    "--model-id", "toy", "--model-revision", "r1", "--backend", "python",
                    "--backend-revision", "r1", "--out", str(root / "run")]
            with patch("datajevbench.cli.verify_assets", return_value=assets()), redirect_stdout(io.StringIO()):
                main(argv)
                meta = json.loads((root / "run/environment.json").read_text())
                hashes = meta["identity"]["adapter_sources_sha256"]
                self.assertIn(str(helper.resolve()), hashes)
                self.assertIn(str(Path(__file__).resolve()), hashes)
                main(argv + ["--resume"])
                helper.write_text("revision = 2\n")
                with self.assertRaisesRegex(ValueError, "identical identity"):
                    main(argv + ["--resume"])

    def test_critical_backend_failure_stops_and_preserves_attempts(self):
        class Failure(RuntimeError):
            critical = True
            attempts = [{"http_status": 401}]
        engine = self.make_engine()
        with patch.object(engine.backend, "predict", side_effect=Failure("authentication failed")):
            with self.assertRaises(CriticalInferenceError) as caught:
                engine(request())
        self.assertEqual(caught.exception.attempts, [{"http_status": 401}])


if __name__ == "__main__":
    unittest.main()
