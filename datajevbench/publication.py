"""Stable public identifiers and a minimal, non-scoring metadata projection."""

import copy
import hashlib
import json
import re


FORMAT = "datajevbench.public.v1"
PROVENANCE_FIELDS = (
    "subset", "source", "source_url", "license", "source_sha256",
    "operator_document_sha256", "reference_type",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def public_id(task):
    # Expected answers, old IDs and construction metadata never enter this digest.
    identity = {"schema": FORMAT, "subset": task["provenance"]["subset"],
                **{key: task[key] for key in ("state", "question", "labels")}}
    return f"{identity['subset']}-{hashlib.sha256(canonical(identity)).hexdigest()[:16]}"


def public_group(group):
    if group is None:
        return None
    return "G-" + hashlib.sha256(canonical({"schema": FORMAT, "group": group})).hexdigest()[:16]


def public_record(task):
    result = copy.deepcopy(task)
    result["id"] = public_id(task)
    result["group"] = public_group(task["group"])
    provenance = task["provenance"]
    result["provenance"] = {key: copy.deepcopy(provenance[key]) for key in PROVENANCE_FIELDS}
    result["provenance"]["language"] = {"task_language": provenance["language"]["task_language"]}
    caveats = sorted({value for tag in provenance.get("review_tags", []) if isinstance(tag, dict)
                     for value in tag.get("reference_caveats", [])})
    if caveats:
        result["provenance"]["reference_caveats"] = caveats
    return result


def semantic_digest(tasks):
    """Fingerprint ordered model content, labels and scoring references, excluding IDs."""
    content = [{**{key: task[key] for key in ("family", "state", "question", "labels", "expected", "split")},
                "subset": task["provenance"]["subset"]} for task in tasks]
    return hashlib.sha256(canonical(content)).hexdigest()


def wire_digest(inputs):
    """Hash ordered HTTP-visible requests, preserving all nested candidate ordering."""
    wire = [{"state": row["state"], "questions": {"decision": row["question"]}} for row in inputs]
    return hashlib.sha256(json.dumps(wire, ensure_ascii=False, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def validate_publication(tasks, inputs, publication):
    if publication.get("format") != FORMAT:
        raise ValueError("Unknown public data format")
    allowed = set(PROVENANCE_FIELDS) | {"language", "reference_caveats"}
    required = set(PROVENANCE_FIELDS) | {"language"}
    for task in tasks:
        if task["id"] != public_id(task):
            raise ValueError("Public task ID differs from its model-visible content")
        if task["group"] is not None and not re.fullmatch(r"G-[0-9a-f]{16}", task["group"]):
            raise ValueError("Non-public group identifier")
        provenance = task["provenance"]
        if not required <= set(provenance) <= allowed:
            raise ValueError("Public provenance contains missing or non-public fields")
        if set(provenance["language"]) != {"task_language"}:
            raise ValueError("Public language metadata contains construction details")
    if semantic_digest(tasks) != publication["semantic_sha256"]:
        raise ValueError("Public task/reference content fingerprint differs")
    if wire_digest(inputs) != publication["model_wire_sha256"]:
        raise ValueError("Model-visible request fingerprint differs")
