"""Validate the public result snapshot and sync the two README tables."""

import argparse
from datetime import date
import json
import math
from pathlib import Path
import re


START = "<!-- results:start -->"
END = "<!-- results:end -->"


def ranked_entries(board):
    rows = sorted(board["entries"], key=lambda r: (-r["overall"]["accuracy"], r["model"].casefold(), r["id"]))
    rank, previous = 0, None
    for index, row in enumerate(rows, 1):
        score = row["overall"]["accuracy"]
        if score != previous:
            rank, previous = index, score
        yield rank, row


def validate_board(board, manifest):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(board["schema"] == "datajevbench.board.v1" and board["metric"] == "micro_accuracy", "Board format")
    require(board["release"] == manifest["version"] and board["probability_sum_abs_tol"] == 1e-3, "Board release policy")
    # Historical results retain the hashes of the source IDs used for those runs.
    snapshot_files = manifest.get("source_files", manifest["files"])
    for field, asset in (("dataset_sha256", "data-jevbench-v0.5.jsonl"),
                         ("inputs_sha256", "inputs.jsonl"), ("scorer_sha256", "contract.py")):
        require(board[field] == snapshot_files[asset]["sha256"], f"Board {field}")
    date.fromisoformat(board["evaluated_at"])
    ids = set()

    def check_score(score, total):
        require(score["total"] == total, "Score denominator")
        for key in ("total", "valid", "missing", "correct", "probabilistic"):
            require(type(score[key]) is int, f"Integer count: {key}")
        require(0 <= score["correct"] <= score["valid"] <= total, "Score counts")
        require(0 <= score["probabilistic"] <= score["valid"], "Probability coverage")
        require(score["missing"] == total - score["valid"], "Missing count")
        require(score["accuracy"] == score["correct"] / total, "Accuracy denominator")
        for key, maximum in (("ece", 1), ("brier", 2)):
            value = score[key]
            if score["probabilistic"] == total:
                require(type(value) in (float, int) and math.isfinite(value) and 0 <= value <= maximum, f"Valid {key}")
            else:
                require(value is None, f"Incomplete {key} coverage")

    for row in board["entries"]:
        require(isinstance(row["id"], str) and re.fullmatch(r"[a-z0-9-]+", row["id"]), "Entry ID")
        require(row["id"] not in ids, "Duplicate entry ID")
        ids.add(row["id"])
        for field in ("model", "model_id", "backend", "inference_note"):
            require(isinstance(row[field], str) and row[field].strip(), f"Missing {field}")
        date.fromisoformat(row["evaluated_at"])
        require(row["model_revision"] is None or isinstance(row["model_revision"], str), "Model revision")
        require(isinstance(row["settings"], dict), "Inference settings")
        check_score(row["overall"], manifest["records"])
        require(set(row["by_subset"]) == set(manifest["by_subset"]), "Subset IDs")
        for key, total in manifest["by_subset"].items():
            check_score(row["by_subset"][key], total)
        for key in ("total", "valid", "missing", "correct", "probabilistic"):
            require(sum(s[key] for s in row["by_subset"].values()) == row["overall"][key], f"Subset {key} sum")
        if row["overall"]["brier"] is not None:
            weighted = sum(s["brier"] * s["total"] for s in row["by_subset"].values()) / manifest["records"]
            require(math.isclose(weighted, row["overall"]["brier"], rel_tol=0, abs_tol=1e-12), "Subset Brier aggregation")
        for key in ("raw_results_sha256", "predictions_sha256", "source_scores_sha256"):
            require(bool(re.fullmatch(r"[0-9a-f]{64}", row["evidence"][key])), f"Evidence hash: {key}")


def result_table(board, chinese=False):
    header = "| 名次 | 模型 | Accuracy ↑ | 有效回答 | ECE10 ↓ | Brier ↓ |" if chinese else "| Rank | Model | Accuracy ↑ | Valid answers | ECE10 ↓ | Brier ↓ |"
    lines = [header, "| ---: | --- | ---: | ---: | ---: | ---: |"]
    number = lambda value: "—" if value is None else f"{value:.4f}"
    for rank, row in ranked_entries(board):
        s = row["overall"]
        name = row["model"].replace("|", "&#124;").replace("\n", " ")
        lines.append(f"| {rank} | {name} | {s['accuracy']:.1%} | {s['valid']}/{s['total']} | {number(s['ece'])} | {number(s['brier'])} |")
    return "\n".join(lines)


def sync_readmes(root, board, check=False):
    for name in ("README.md", "README.zh-CN.md"):
        path = root / name
        text = path.read_text(encoding="utf-8")
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError(f"{name}: result table markers")
        before, rest = text.split(START)
        old, after = rest.split(END)
        chinese = name.endswith("zh-CN.md")
        label = "评测快照" if chinese else "Evaluation snapshot"
        content = f"\n\n{label}: **{board['evaluated_at']}**\n\n" + result_table(board, chinese) + "\n\n"
        if check and old != content:
            raise ValueError(f"{name}: run python scripts/render_results.py")
        if not check and old != content:
            path.write_text(before + START + content + END + after, encoding="utf-8")


def check(root):
    board = json.loads((root / "results/leaderboard.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "releases/v0.5/manifest.json").read_text(encoding="utf-8"))
    validate_board(board, manifest)
    sync_readmes(root, board, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without writing files")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    board = json.loads((root / "results/leaderboard.json").read_text(encoding="utf-8"))
    validate_board(board, json.loads((root / "releases/v0.5/manifest.json").read_text(encoding="utf-8")))
    sync_readmes(root, board, args.check)
    print(f"Result snapshot checked: {len(board['entries'])} models")
