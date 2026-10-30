"""Run the repository's CPU-only checks with artifacts outside the checkout."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from check_public import check


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    print(f"Public source checks passed: {check(root)} files", flush=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root))
    with tempfile.TemporaryDirectory(prefix="datajevbench-check-") as tmp:
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"],
                       cwd=tmp, env=env, check=True)
        subprocess.run([sys.executable, "-m", "datajevbench.cli", "doctor", "--engine",
                        "datajevbench.engines:create_http", "--engine-options",
                        str(root / "configs/systemone.example.json"), "--model-id", "your-model"],
                       cwd=tmp, env=env, check=True)
    print("Repository checks passed")


if __name__ == "__main__":
    main()
