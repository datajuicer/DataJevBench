"""DataJevBench v0.5 task validation and scoring; probability sum tolerance 1e-3."""

import copy
import math

PROBABILITY_SUM_ABS_TOL = 1e-3

FAMILIES = {
    "D1": "policy", "D2": "routing", "D3": "ordinal",
    "D4": "adequacy", "D5": "policy", "D6": "intent",
}
FIELDS = {"id", "family", "state", "question", "labels", "expected", "split", "group", "provenance"}


def validate(row):
    if set(row) != FIELDS:
        raise ValueError("Task fields do not match the portable contract")
    if not isinstance(row["id"], str) or not row["id"]:
        raise ValueError("Empty id")
    labels, q = row["labels"], row["question"]
    if not labels or len(labels) != len(set(labels)) or not all(isinstance(x, str) for x in labels):
        raise ValueError("Labels must be distinct strings")
    if row["family"] not in set(FAMILIES.values()) or row["split"] not in {"public", "private"}:
        raise ValueError("Invalid family or split")
    if not isinstance(q["instructions"], str) or not q["instructions"]:
        raise ValueError("Missing instructions")
    if q["type"] == "score":
        if type(row["expected"]) is not int or str(row["expected"]) not in labels:
            raise ValueError("Score expected must be an integer level index")
        if not isinstance(q["criteria"], list) or labels != [str(i) for i in range(len(q["criteria"]))]:
            raise ValueError("Score criteria and labels disagree")
    elif q["type"] == "choice":
        if not isinstance(q["criteria"], dict) or list(q["criteria"]) != labels or row["expected"] not in labels:
            raise ValueError("Choice criteria, labels or expected disagree")
    else:
        raise ValueError("Only current Choice/Score tasks are exported")


def model_input(row):
    """Allowlist prevents gold and semantic metadata leaking into a model request."""
    return copy.deepcopy({key: row[key] for key in ("id", "state", "question", "labels")})


def score_predictions(tasks, predictions):
    """Micro Accuracy; ECE10/Brier only for complete valid probability predictions.

    Label-only predictions remain label-only. Unknown, duplicate, inconsistent or
    malformed predictions fail explicitly; missing rows count as incorrect.
    """
    by_id = {t["id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Duplicate task id")
    seen, valid, correct, bins, brier, probabilistic = set(), 0, 0, [[0, 0, 0] for _ in range(10)], 0.0, 0
    for p in predictions:
        iid = p["id"]
        if iid in seen or iid not in by_id:
            raise ValueError("Duplicate or unknown prediction id")
        seen.add(iid)
        row = by_id[iid]
        answer = str(p["answer"])
        if answer not in row["labels"]:
            raise ValueError("Prediction is not an allowed label")
        hit = answer == str(row["expected"])
        valid += 1
        correct += hit
        probs = p.get("probabilities")
        if probs is not None:
            if not isinstance(probs, dict) or set(probs) != set(row["labels"]) or any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in probs.values()):
                raise ValueError("Malformed probabilities")
            if not math.isclose(sum(probs.values()), 1, rel_tol=0.0, abs_tol=PROBABILITY_SUM_ABS_TOL):
                raise ValueError("Probabilities must sum to one")
            # Upstream JevBench breaks exact probability ties lexicographically.
            winner = min(probs, key=lambda k: (-probs[k], k))
            if answer != winner:
                raise ValueError("Answer and probability argmax disagree")
            confidence = probs[answer]
            b = bins[min(9, int(confidence * 10))]
            b[0] += 1
            b[1] += confidence
            b[2] += hit
            brier += sum((v - (k == str(row["expected"]))) ** 2 for k, v in probs.items())
            probabilistic += 1
    n = len(tasks)
    return {"total": n, "valid": valid, "missing": n - valid, "correct": correct,
            "accuracy": correct / n if n else None, "probabilistic": probabilistic,
            "ece": sum(abs(b[1] - b[2]) for b in bins) / n if n and probabilistic == n else None,
            "brier": brier / n if n and probabilistic == n else None}
