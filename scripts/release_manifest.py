"""Generate or check the source publication manifest independently of task version."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


PUBLICATION_VERSION = "0.5.4"
PUBLICATION_MANIFEST = "releases/publication.json"
DATA_FILES = ("benchmark/records.jsonl", "benchmark/inputs.jsonl")


def source_files(root):
    root = Path(root).resolve()
    result = (subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                            capture_output=True, text=True) if shutil.which("git") else None)
    if result is not None and result.returncode == 0 and Path(result.stdout.strip()).resolve() == root:
        names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others",
                                         "--exclude-standard"], cwd=root).decode().split("\0")
        return sorted({root / name for name in names if name and
                       ((root / name).exists() or (root / name).is_symlink())})
    return sorted(path for path in root.rglob("*") if path.is_file() or path.is_symlink())


def build_manifest(root):
    root = Path(root).resolve()
    release = json.loads((root / "releases/v0.5/manifest.json").read_text(encoding="utf-8"))
    present = [(root / name).is_file() for name in DATA_FILES]
    if any(present) and not all(present):
        raise ValueError("Import both benchmark/records.jsonl and benchmark/inputs.jsonl together")
    hashes = {}
    for path in source_files(root):
        name = path.relative_to(root).as_posix()
        if name == PUBLICATION_MANIFEST:
            continue
        if path.is_symlink():
            raise ValueError(f"Source manifest cannot include a symlink: {name}")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema": "datajevbench.publication.v1",
        "benchmark": "DataJevBench",
        "benchmark_version": release["version"],
        "release_version": PUBLICATION_VERSION,
        "algorithm": "sha256",
        "content_manifest": "releases/v0.5/manifest.json",
        "data": {
            "status": "included" if all(present) else "pending_import",
            "records": {"path": DATA_FILES[0],
                        "sha256": release["files"]["data-jevbench-v0.5.jsonl"]["sha256"]},
            "inputs": {"path": DATA_FILES[1],
                       "sha256": release["files"]["inputs.jsonl"]["sha256"]},
        },
        "historical_predictions": {"status": "not_bundled"},
        "files": hashes,
    }


def check_manifest(root):
    path = Path(root) / PUBLICATION_MANIFEST
    expected = build_manifest(root)
    if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != expected:
        raise ValueError("Source manifest is stale; run python scripts/release_manifest.py --write")
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"Regenerate {PUBLICATION_MANIFEST}")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.write:
        manifest = build_manifest(root)
        (root / PUBLICATION_MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    else:
        manifest = check_manifest(root)
    print(f"Source publication {manifest['release_version']}: {len(manifest['files'])} files; "
          f"data {manifest['data']['status']}")


if __name__ == "__main__":
    main()
