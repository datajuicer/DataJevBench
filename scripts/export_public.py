"""Export and test a committed source archive."""

import argparse
import gzip
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
from check_public import check


def export(output):
    root = Path(__file__).resolve().parents[1]
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
        raise ValueError("Commit local changes before exporting")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    archive = subprocess.check_output(["git", "archive", "--format=tar", "--prefix=DataJevBench/", "HEAD"], cwd=root)
    with tempfile.TemporaryDirectory(prefix="datajevbench-public-") as tmp:
        destination = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            for member in bundle.getmembers():
                target = destination / member.name
                if (not target.resolve().is_relative_to(destination) or
                        not (member.isfile() or member.isdir())):
                    raise ValueError("Archive contains an unsafe path or unsupported member")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.extractfile(member).read())
        snapshot = destination / "DataJevBench"
        count = check(snapshot)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(snapshot))
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(snapshot / "tests"), "-v"],
                       cwd=tmp, env=env, check=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(archive)
    print(f"Exported {count} checked files: {output}")
    print(f"SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args().output.resolve())
