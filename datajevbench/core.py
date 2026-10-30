"""Pinned DataJevBench v0.5 task checks, model runs and scoring."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .contract_v05 import PROBABILITY_SUM_ABS_TOL, model_input, score_predictions, validate


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "0.5"
RELEASE = ROOT / "releases" / "v0.5"
if not (RELEASE / "manifest.json").is_file():
    RELEASE = Path(__file__).with_name("_data")
SCORER = Path(__file__).with_name("contract_v05.py")


class CriticalInferenceError(RuntimeError):
    """A model or service failure that stops the run."""

    def __init__(self, message: str, attempts: list[dict] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if line.strip():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_no}: expected object")
                rows.append(row)
    return rows


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_assets(dataset: Path, inputs: Path, manifest_path: Path = RELEASE / "manifest.json") -> dict:
    manifest = read_json(manifest_path)
    for path, name in ((dataset, "data-jevbench-v0.5.jsonl"), (inputs, "inputs.jsonl")):
        expected = manifest["files"][name]["sha256"]
        if sha256(path) != expected:
            raise ValueError(f"{name}: SHA256 differs from v0.5 task release")
    if manifest_path == RELEASE / "manifest.json" and sha256(SCORER) != manifest["files"]["contract.py"]["sha256"]:
        raise ValueError("Bundled v0.5 scorer differs from the release manifest")

    tasks, requests = read_jsonl(dataset), read_jsonl(inputs)
    if len(tasks) != manifest["records"] or len(requests) != len(tasks):
        raise ValueError("Dataset/input row count differs from the release")
    task_ids = set()
    subset_counts = Counter()
    for task in tasks:
        validate(task)
        if task["id"] in task_ids:
            raise ValueError(f"Duplicate task id: {task['id']}")
        task_ids.add(task["id"])
        subset_counts[task["provenance"]["subset"]] += 1
    if dict(subset_counts) != manifest["by_subset"]:
        raise ValueError("Subset counts differ from release manifest")
    request_ids = set()
    by_id = {task["id"]: task for task in tasks}
    for request in requests:
        if set(request) != {"id", "state", "question", "labels"}:
            raise ValueError("Model input contains extra or missing fields")
        iid = request["id"]
        if iid in request_ids or iid not in by_id:
            raise ValueError(f"Duplicate or unknown input id: {iid}")
        request_ids.add(iid)
        if request != model_input(by_id[iid]):
            raise ValueError(f"Input differs from gold-free projection: {iid}")
    if "publication" in manifest:
        from .publication import validate_publication
        validate_publication(tasks, requests, manifest["publication"])
    return {"tasks": tasks, "inputs": requests, "manifest": manifest,
            "dataset_sha256": sha256(dataset), "inputs_sha256": sha256(inputs),
            "scorer_sha256": sha256(SCORER)}


def validate_response(request: dict, output: object) -> dict:
    if not isinstance(output, dict) or "answer" not in output:
        raise ValueError("Engine must return an object with answer")
    answer = str(output["answer"])
    labels = request["labels"]
    if answer not in labels:
        raise ValueError("Answer is not an allowed label")
    prediction = {"id": request["id"], "answer": answer}
    if "probabilities" in output and output["probabilities"] is not None:
        probs = output["probabilities"]
        if not isinstance(probs, dict) or set(probs) != set(labels):
            raise ValueError("Probabilities must cover every label")
        if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probs.values()):
            raise ValueError("Probabilities must be finite numbers in [0, 1]")
        if not math.isclose(sum(probs.values()), 1, rel_tol=0.0, abs_tol=PROBABILITY_SUM_ABS_TOL):
            raise ValueError("Probabilities must sum to one")
        if answer != min(probs, key=lambda key: (-probs[key], key)):
            raise ValueError("Answer and probability argmax disagree")
        prediction["probabilities"] = probs
    return prediction


def load_engine(spec: str, options: dict):
    if ":" not in spec:
        raise ValueError("Engine must use module:factory syntax")
    module_name, attribute = spec.split(":", 1)
    factory = getattr(importlib.import_module(module_name), attribute)
    engine = factory(**options)
    if not callable(engine):
        raise TypeError("Engine factory must return a callable")
    return engine


def latest_events(path: Path, known_ids: set[str]) -> dict[str, dict]:
    latest = {}
    if path.exists():
        for event in read_jsonl(path):
            iid = event.get("id")
            if iid not in known_ids or event.get("status") not in {"ok", "error"}:
                raise ValueError("Run log contains an unknown id or status")
            if event.get("attempt") != (latest.get(iid, {}).get("attempt", 0) + 1):
                raise ValueError(f"Run log attempt sequence invalid for {iid}")
            latest[iid] = event
    return latest


def run_evaluation(assets: dict, out: Path, engine, identity: dict, resume: bool = False,
                   limit: int | None = None) -> dict:
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("limit must be a positive integer")
    if limit is not None and limit >= len(assets["inputs"]):
        raise ValueError("Diagnostic limit must be smaller than the full task set")
    out.mkdir(parents=True, exist_ok=True)
    metadata_path, results_path = out / "environment.json", out / "results.jsonl"
    metadata = {"schema": "datajevbench.run.v1", "release": RELEASE_VERSION,
                "dataset_sha256": assets["dataset_sha256"], "inputs_sha256": assets["inputs_sha256"],
                "scorer_sha256": assets["scorer_sha256"], "identity": identity}
    if limit is not None:
        metadata["limit"] = limit
    if metadata_path.exists():
        if not resume or read_json(metadata_path) != metadata:
            raise ValueError("Run directory exists; use --resume with identical identity and assets")
    elif results_path.exists():
        raise ValueError("Run log exists without environment.json")
    else:
        write_json(metadata_path, metadata)
    selected = assets["inputs"] if limit is None else assets["inputs"][:limit]
    known_ids = {request["id"] for request in selected}
    latest = latest_events(results_path, known_ids)
    pinned = [event["raw_output"]["_service_identity"] for event in latest.values()
              if event["status"] == "ok" and isinstance(event.get("raw_output"), dict)
              and "_service_identity" in event["raw_output"]]
    if pinned:
        if len({json_hash(value) for value in pinned}) != 1:
            raise ValueError("Run log contains multiple service identities")
        if hasattr(engine, "bind_identity"):
            engine.bind_identity(pinned[0])
    with results_path.open("a", encoding="utf-8") as stream:
        for request in selected:
            iid = request["id"]
            if latest.get(iid, {}).get("status") == "ok":
                continue
            start = time.perf_counter()
            event = {"id": iid, "attempt": latest.get(iid, {}).get("attempt", 0) + 1,
                     "input_sha256": json_hash(request), "started_utc": datetime.now(timezone.utc).isoformat()}
            critical_error = None
            try:
                output = engine(copy.deepcopy(request))
                prediction = validate_response(request, output)
                json.dumps(output, ensure_ascii=False, allow_nan=False)
                event.update({"status": "ok", "prediction": prediction, "raw_output": output})
            except Exception as exc:
                event.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
                if getattr(exc, "attempts", None):
                    event["transport_attempts"] = exc.attempts
                if isinstance(exc, CriticalInferenceError):
                    critical_error = exc
                    event["fatal"] = True
            event["wall_ms"] = round((time.perf_counter() - start) * 1000, 3)
            event["completed_utc"] = datetime.now(timezone.utc).isoformat()
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            latest[iid] = event
            if critical_error is not None:
                raise critical_error
    return {"attempted": len(latest), "valid": sum(event["status"] == "ok" for event in latest.values()),
            "total": len(selected), "results": str(results_path)}


def score_run(assets: dict, run_dir: Path, write: bool = True) -> dict:
    metadata_path, results_path = run_dir / "environment.json", run_dir / "results.jsonl"
    metadata = read_json(metadata_path)
    if metadata.get("schema") != "datajevbench.run.v1" or metadata.get("release") != RELEASE_VERSION:
        raise ValueError("Unsupported run metadata")
    for field in ("dataset_sha256", "inputs_sha256", "scorer_sha256"):
        if metadata.get(field) != assets[field]:
            raise ValueError(f"Run {field} differs from verified release")
    requests = {row["id"]: row for row in assets["inputs"]}
    latest = latest_events(results_path, set(requests))
    predictions = []
    service_identities = []
    http_run = metadata["identity"].get("engine") == "datajevbench.engines:create_http"
    predict_run = metadata["identity"].get("engine") == "datajevbench.predict:create_predict"
    for iid, event in latest.items():
        if event.get("input_sha256") != json_hash(requests[iid]):
            raise ValueError(f"Request hash differs for {iid}")
        if event["status"] == "ok":
            raw_output = event.get("raw_output")
            if not isinstance(raw_output, dict):
                raise ValueError(f"Saved model output is not an object: {iid}")
            if http_run:
                service_identity = raw_output.get("_service_identity")
                if not isinstance(service_identity, dict):
                    raise ValueError(f"HTTP result lacks service identity: {iid}")
                from .engines import SystemOneHTTP
                replayed = SystemOneHTTP.normalize_response(raw_output.get("_http_response"), requests[iid])
                for field in ("answer", "probabilities", "_service_identity"):
                    if replayed.get(field) != raw_output.get(field):
                        raise ValueError(f"HTTP normalization differs from saved raw response: {iid}")
                options = metadata["identity"]["engine_options"]
                pins = options.get("expected_returned_models")
                if pins and service_identity["model"] not in pins:
                    raise ValueError(f"HTTP returned model differs from configured pins: {iid}")
                wire = SystemOneHTTP.wire_payload(requests[iid], options["model_id"])
                request_bytes = json.dumps(wire, ensure_ascii=False, separators=(",", ":"),
                                           allow_nan=False).encode()
                if raw_output.get("_http_receipt", {}).get("request_sha256") != hashlib.sha256(request_bytes).hexdigest():
                    raise ValueError(f"HTTP request hash differs from frozen projection: {iid}")
                service_identities.append(service_identity)
            if predict_run:
                from .engines import normalize_answers
                replayed = normalize_answers(raw_output.get("_predict_response"), requests[iid])
                if any(replayed.get(field) != raw_output.get(field) for field in ("answer", "probabilities")):
                    raise ValueError(f"Predict normalization differs from saved raw response: {iid}")
            prediction = validate_response(requests[iid], raw_output)
            if event.get("prediction") != prediction:
                raise ValueError(f"Saved prediction differs from raw response for {iid}")
            predictions.append(prediction)
    if len({json_hash(value) for value in service_identities}) > 1:
        raise ValueError("HTTP results contain multiple service identities")
    tasks = assets["tasks"]
    overall = score_predictions(tasks, predictions)
    by_subset = {}
    for subset in sorted(assets["manifest"]["by_subset"]):
        rows = [task for task in tasks if task["provenance"]["subset"] == subset]
        ids = {task["id"] for task in rows}
        by_subset[subset] = score_predictions(rows, [p for p in predictions if p["id"] in ids])
    result = {"schema": "datajevbench.scores.v1", "release": RELEASE_VERSION,
              "dataset_sha256": assets["dataset_sha256"], "inputs_sha256": assets["inputs_sha256"],
              "scorer_sha256": assets["scorer_sha256"], "environment_sha256": sha256(metadata_path),
              "results_sha256": sha256(results_path), "identity": metadata["identity"],
              "complete": len(latest) == len(requests), "attempted": len(latest),
              "errors": sum(event["status"] == "error" for event in latest.values()),
              "fatal_errors": sum(bool(event.get("fatal")) for event in latest.values()),
              "overall": overall, "by_subset": by_subset}
    if service_identities:
        result["service_identity"] = service_identities[0]
    if write:
        write_json(run_dir / "scores.json", result)
    return result
