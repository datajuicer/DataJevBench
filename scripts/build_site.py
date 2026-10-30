"""Export the static site with generated copies of shared assets and published results."""

import argparse
from pathlib import Path
import shutil

from render_results import check


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    check(root)
    if output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    if output.is_relative_to(root) and not any(
            output.is_relative_to(root / name) for name in ("build", "dist")):
        raise ValueError("Use build/, dist/ or a directory outside the repository for site exports")
    output.mkdir(parents=True)
    for path in (root / "site").iterdir():
        if path.is_file():
            if path.suffix in {".html", ".js"}:
                text = path.read_text(encoding="utf-8")
                text = text.replace("../assets/", "assets/").replace("../results/", "results/")
                (output / path.name).write_text(text, encoding="utf-8")
            else:
                shutil.copy2(path, output / path.name)
    shutil.copytree(root / "assets", output / "assets")
    (output / "results").mkdir()
    shutil.copy2(root / "results/leaderboard.json", output / "results/leaderboard.json")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(f"Static site exported: {build(Path(__file__).resolve().parents[1], args.output)}")
