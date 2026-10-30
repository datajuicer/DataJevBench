"""Reproduce the public data projection from the frozen original v0.5 source pair."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datajevbench.contract_v05 import model_input
from datajevbench.core import verify_assets
from datajevbench.publication import FORMAT, PROVENANCE_FIELDS, public_record, semantic_digest, wire_digest


def encode_rows(rows):
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":"),
                              allow_nan=False) + "\n" for row in rows)


def prepare(dataset, inputs, source_manifest):
    assets = verify_assets(Path(dataset), Path(inputs), Path(source_manifest))
    original = assets["tasks"]
    records = [public_record(task) for task in original]
    projected = [model_input(task) for task in records]
    by_id = {row["id"]: row for row in projected}
    if len(by_id) != len(records):
        raise ValueError("Public ID collision or duplicate visible task; do not assign order-based suffixes")
    groups = {}
    for old, new in zip(original, records):
        if new["group"] in groups and groups[new["group"]] != old["group"]:
            raise ValueError("Public group hash collision")
        groups[new["group"]] = old["group"]
    old_to_new = {old["id"]: new["id"] for old, new in zip(original, records)}
    # Retain the original input file's order even if it differs from task order.
    projected = [by_id[old_to_new[row["id"]]] for row in assets["inputs"]]
    for old, new in zip(original, records):
        for key in ("family", "state", "question", "labels", "expected", "split"):
            if old[key] != new[key]:
                raise ValueError(f"Scoring content changed: {key}")
        if list(old["question"]["criteria"]) != list(new["question"]["criteria"]):
            raise ValueError("Candidate order changed")
    semantic = semantic_digest(original)
    wire = wire_digest(assets["inputs"])
    if semantic_digest(records) != semantic or wire_digest(projected) != wire:
        raise ValueError("Published content differs from the original model/scoring content")
    files = {"records.jsonl": encode_rows(records), "inputs.jsonl": encode_rows(projected)}
    manifest = copy.deepcopy(assets["manifest"])
    manifest["status"] = "public_data_included"
    manifest["source_files"] = copy.deepcopy(manifest["files"])
    for filename, source_name in (("records.jsonl", "data-jevbench-v0.5.jsonl"), ("inputs.jsonl", "inputs.jsonl")):
        content = files[filename].encode("utf-8")
        manifest["files"][source_name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    manifest["publication"] = {
        "format": FORMAT,
        "id_scheme": "D{subset}-sha256(schema,subset,state,question,ordered-labels)[:16]",
        "group_scheme": "G-sha256(schema,original-group)[:16]",
        "id_hash_uses_reference_answers": False,
        "provenance_fields": list(PROVENANCE_FIELDS) + ["language.task_language", "reference_caveats (when present)"],
        "semantic_sha256": semantic,
        "model_wire_sha256": wire,
        "historical_snapshot_identity": "source_files",
    }
    report = {
        "source_dataset_sha256": assets["dataset_sha256"],
        "source_inputs_sha256": assets["inputs_sha256"],
        "public_dataset_sha256": manifest["files"]["data-jevbench-v0.5.jsonl"]["sha256"],
        "public_inputs_sha256": manifest["files"]["inputs.jsonl"]["sha256"],
        "records": len(records), "format": FORMAT,
        "semantic_sha256": semantic, "model_wire_sha256": wire,
        "reference_and_model_content_unchanged": True,
        "removed_provenance_fields": sorted(set().union(*(set(t["provenance"]) for t in original)) -
                                            set(PROVENANCE_FIELDS) - {"language"}),
        "id_map": [{"source_id": old["id"], "public_id": new["id"],
                    "source_group": old["group"], "public_group": new["group"]}
                   for old, new in zip(original, records)],
    }
    return files, manifest, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New staging directory outside the Git repository; includes private audit mapping")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("Use a staging directory outside the repository; audit mappings are not public assets")
    files, manifest, report = prepare(args.dataset, args.inputs, args.source_manifest)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        (output / name).write_text(content, encoding="utf-8")
    for name, value in (("manifest.json", manifest), ("id-audit.private.json", report)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {report['records']} public tasks in {output}; audit mapping stays outside source control")


if __name__ == "__main__":
    main()
