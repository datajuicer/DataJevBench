"""Check distributable files, pinned scoring metadata and local documentation links."""

import hashlib
import json
from pathlib import Path
import re

from render_results import check as check_results
from release_manifest import DATA_FILES, check_manifest, source_files


PATTERNS = {
    "private key": r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",
    "credential": r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|AKIA[A-Z0-9]{16})\b",
    "internal host": r"\b[\w.-]+\.(?:internal|corp|lan)\.com\b",
    "private IPv4": r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b",
    "workstation path": r"/(?:mnt|home|root)/[^\s\"'<>]+|workspaces/[\w.-]+/(?:reports|runtime)/",
}


def check(root):
    root = Path(root).resolve()
    errors = []
    paths = source_files(root)
    data_present = [(root / name).is_file() for name in DATA_FILES]
    if any(data_present):
        if not all(data_present):
            errors.append("Public task data must contain both records.jsonl and inputs.jsonl")
        else:
            from datajevbench.core import verify_assets
            try:
                verify_assets(root / DATA_FILES[0], root / DATA_FILES[1],
                              root / "releases/v0.5/manifest.json")
            except (ValueError, KeyError, TypeError, OSError) as exc:
                errors.append(f"Public task data: {exc}")
    for path in paths:
        relative = path.relative_to(root)
        if relative.as_posix() in DATA_FILES and not path.is_symlink():
            # Only the approved, hash-verified data pair is allowed as public JSONL.
            continue
        if (path.is_symlink() or any(part in {".git", ".venv", "__pycache__", "runs", "work"} for part in relative.parts)
                or path.name.startswith(".env") or path.name.endswith(".local.json")
                or path.suffix in {".jsonl", ".pem", ".key", ".p12", ".safetensors", ".pt", ".pth", ".bin"}):
            errors.append(f"{relative}: non-public artifact")
            continue
        if path.suffix == ".png":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeError:
            errors.append(f"{relative}: unexpected binary file")
            continue
        for label, pattern in PATTERNS.items():
            for match in re.finditer(pattern, content):
                # Report locations, never the potentially sensitive matched value.
                errors.append(f"{relative}:{content.count(chr(10), 0, match.start()) + 1}: {label}")
        if path.suffix in {".md", ".html"}:
            targets = re.findall(r'\[[^\]\n]*\]\(([^)\s]+)\)', content)
            targets += re.findall(r'(?:href|src)=[\"\']([^\"\']+)[\"\']', content)
            for target in targets:
                if re.match(r"[a-z]+:|#|//", target):
                    continue
                local = target.split("#", 1)[0].split("?", 1)[0]
                if local and not (path.parent / local).exists():
                    errors.append(f"{relative}: missing local link {local}")
    manifest = json.loads((root / "releases/v0.5/manifest.json").read_text())
    if manifest.get("status") == "public_data_included" and not all(data_present):
        errors.append("Release declares public data but the task/input pair is missing")
    policy = manifest["scoring_policy"]
    scorer = root / policy["scorer_module"]
    if (manifest["version"] != "0.5" or policy["probability_sum_abs_tol"] != 1e-3
            or policy["probability_sum_rel_tol"] != 0 or policy["renormalize_probabilities"]):
        errors.append("Release policy differs from v0.5")
    pinned = manifest["files"]["contract.py"]
    if hashlib.sha256(scorer.read_bytes()).hexdigest() != pinned["sha256"] or scorer.stat().st_size != pinned["bytes"]:
        errors.append("Scorer bytes differ from the release manifest")
    try:
        check_results(root)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"Result snapshot: {exc}")
    if not (root / "LICENSE").is_file():
        errors.append("Missing code license")
    try:
        check_manifest(root)
    except (ValueError, OSError) as exc:
        errors.append(str(exc))
    if errors:
        raise ValueError("\n".join(errors))
    return len(paths)


if __name__ == "__main__":
    try:
        count = check(Path(__file__).resolve().parents[1])
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(f"Public source checks passed: {count} files")
