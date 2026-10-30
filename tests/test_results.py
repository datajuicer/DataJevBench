"""Protect fixed denominators, calibration coverage and competition ranks."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_results", ROOT / "scripts/render_results.py")
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


class ResultsTest(unittest.TestCase):
    def setUp(self):
        self.board = json.loads((ROOT / "results/leaderboard.json").read_text())
        self.manifest = json.loads((ROOT / "releases/v0.5/manifest.json").read_text())

    def test_ranks_use_exact_scores_and_share_ties(self):
        rows = [{"id": name, "model": name, "overall": {"accuracy": score}}
                for name, score in (("a", .8239), ("c", .8241), ("b", .8241))]
        ranked = [(rank, row["id"]) for rank, row in results.ranked_entries({"entries": rows})]
        self.assertEqual(ranked, [(1, "b"), (1, "c"), (3, "a")])

    def test_incomplete_outputs_keep_full_denominator_and_null_calibration(self):
        # Exercise an incomplete snapshot independently of the published model roster.
        original = copy.deepcopy(self.board["entries"][0])
        original["overall"].update(valid=499, missing=1, probabilistic=499, ece=None, brier=None)
        original["by_subset"]["D1"].update(valid=89, missing=1, probabilistic=89, ece=None, brier=None)
        self.board["entries"] = [original]
        results.validate_board(self.board, self.manifest)
        for field, value in (("accuracy", original["overall"]["correct"] / 499), ("ece", 0.02), ("brier", 0.2)):
            altered = copy.deepcopy(self.board)
            altered["entries"][0]["overall"][field] = value
            with self.assertRaises(ValueError):
                results.validate_board(altered, self.manifest)

    def test_subset_counts_must_add_up_to_overall(self):
        subset = self.board["entries"][0]["by_subset"]["D1"]
        subset["correct"] -= 1
        subset["accuracy"] = subset["correct"] / subset["total"]
        with self.assertRaisesRegex(ValueError, "Subset correct sum"):
            results.validate_board(self.board, self.manifest)


if __name__ == "__main__":
    unittest.main()
