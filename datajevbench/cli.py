"""Command-line interface for DataJevBench v0.5."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from .core import RELEASE_VERSION, load_engine, read_json, run_evaluation, score_run, sha256, verify_assets


def reject_credentials(value, path="settings"):
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            sensitive = {"token", "access_token", "bearer_token", "auth_token", "hf_token"}
            if lowered in sensitive or any(word in lowered for word in ("secret", "password", "api_key", "authorization", "credential")):
                raise ValueError(f"Credential-like field in {path}.{key}; use environment variables")
            reject_credentials(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_credentials(child, f"{path}[{index}]")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="datajevbench")
    sub = command.add_subparsers(dest="command", required=True)

    def assets_options(item):
        item.add_argument("--dataset", type=Path, default=Path("benchmark/records.jsonl"),
                          help="Frozen v0.5 tasks and references (default: benchmark/records.jsonl)")
        item.add_argument("--inputs", type=Path, default=Path("benchmark/inputs.jsonl"),
                          help="Gold-free inputs (default: benchmark/inputs.jsonl)")

    verify = sub.add_parser("verify", help="Check hashes, 500 tasks and gold-free projection")
    assets_options(verify)

    doctor = sub.add_parser("doctor", help="Check local inference configuration")
    doctor.add_argument("--engine", required=True)
    doctor.add_argument("--engine-options", type=Path)
    doctor.add_argument("--model-id", required=True)

    run = sub.add_parser("run", help="Run a model-provided engine on the pinned inputs")
    assets_options(run)
    run.add_argument("--engine", required=True, help="Python module:factory; factory returns callable")
    run.add_argument("--engine-options", type=Path, help="JSON object passed to the engine factory")
    run.add_argument("--settings", type=Path, required=True, help="JSON record of prompt and inference settings")
    run.add_argument("--model-id", required=True)
    run.add_argument("--model-revision", required=True)
    run.add_argument("--backend", required=True)
    run.add_argument("--backend-revision", required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--limit", type=int, help="Number of tasks in a diagnostic run")
    run.add_argument("--resume", action="store_true")

    score = sub.add_parser("score", help="Score a run with the versioned v0.5 scorer")
    assets_options(score)
    score.add_argument("--run", type=Path, required=True)

    return command


def main(argv: list[str] | None = None) -> None:
    command = parser()
    args = command.parse_args(argv)
    if args.command == "doctor":
        options = read_json(args.engine_options) if args.engine_options else {}
        if not isinstance(options, dict):
            raise ValueError("Engine options must be a JSON object")
        reject_credentials(options, "engine_options")
        if args.engine == "datajevbench.engines:create_http":
            from .engines import SystemOneHTTP
            if options.get("model_id") != args.model_id:
                raise ValueError("HTTP model_id differs from --model-id")
            SystemOneHTTP(**options)
            output = {"engine": args.engine, "configuration_valid": True,
                      "network_calls": 0, "model_loaded": False}
        else:
            if ":" not in args.engine:
                raise ValueError("Engine must use module:factory syntax")
            output = {"engine": args.engine, "configuration_valid": None,
                      "note": "External Python factory is checked when run starts",
                      "network_calls": 0, "model_loaded": False}
    else:
        missing = [str(path) for path in (args.dataset, args.inputs) if not path.is_file()]
        if missing:
            command.error("Task assets unavailable: " + ", ".join(missing) +
                          ". Import the frozen v0.5 files as described in benchmark/README.md, "
                          "or supply --dataset and --inputs.")
        assets = verify_assets(args.dataset, args.inputs)
        if args.command == "verify":
            output = {"release": RELEASE_VERSION, "records": len(assets["tasks"]),
                      "dataset_sha256": assets["dataset_sha256"],
                      "inputs_sha256": assets["inputs_sha256"],
                      "scorer_sha256": assets["scorer_sha256"]}
        elif args.command == "run":
            options = read_json(args.engine_options) if args.engine_options else {}
            settings = read_json(args.settings)
            if not isinstance(options, dict) or not isinstance(settings, dict) or not settings:
                raise ValueError("Engine options and nonempty settings must be JSON objects")
            required = {"inference_method", "input_format", "hardware", "retry_policy"}
            if not required.issubset(settings) or any(not str(settings[key]).strip() for key in required):
                raise ValueError(f"Settings must document {', '.join(sorted(required))}")
            reject_credentials(options, "engine_options")
            reject_credentials(settings)
            identity = {"model_id": args.model_id, "model_revision": args.model_revision,
                        "backend": args.backend, "backend_revision": args.backend_revision,
                        "engine": args.engine, "engine_options": options, "settings": settings}
            if args.engine == "datajevbench.engines:create_http" and options.get("model_id") != args.model_id:
                raise ValueError("HTTP model_id differs from --model-id")
            engine = load_engine(args.engine, options)
            module = importlib.import_module(args.engine.split(":", 1)[0])
            if getattr(module, "__file__", None):
                identity["engine_source_sha256"] = sha256(Path(module.__file__))
            if args.engine == "datajevbench.predict:create_predict":
                identity["adapter_sources_sha256"] = engine.source_hashes
            output = run_evaluation(assets, args.out, engine, identity, args.resume, args.limit)
        elif args.command == "score":
            output = score_run(assets, args.run)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
