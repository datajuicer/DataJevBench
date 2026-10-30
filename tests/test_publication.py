"""Exercise publication integrity, CLI entrypoints and standalone site export."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import build
from release_manifest import PUBLICATION_MANIFEST, build_manifest, check_manifest


class PublicationTest(unittest.TestCase):
    def test_manifest_detects_changed_added_and_removed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / "releases/v0.5/manifest.json"
            release.parent.mkdir(parents=True)
            release.write_bytes((ROOT / "releases/v0.5/manifest.json").read_bytes())
            document = root / "README.md"
            document.write_text("Original publication\n", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertEqual(manifest["data"]["status"], "pending_import")
            self.assertNotIn(PUBLICATION_MANIFEST, manifest["files"])
            (root / PUBLICATION_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(check_manifest(root), manifest)
            document.write_text("Changed publication\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale"):
                check_manifest(root)
            document.write_text("Original publication\n", encoding="utf-8")
            extra = root / "extra.md"
            extra.write_text("New file\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale"):
                check_manifest(root)
            extra.unlink()
            document.unlink()
            with self.assertRaisesRegex(ValueError, "stale"):
                check_manifest(root)
            (root / "benchmark").mkdir()
            (root / "benchmark/records.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Import both"):
                build_manifest(root)

    def test_static_export_resolves_links_and_uses_authoritative_results(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []

            def handle_starttag(self, tag, attrs):
                self.urls.extend(value for key, value in attrs if key in {"src", "href"})

        with tempfile.TemporaryDirectory() as tmp:
            out = build(ROOT, Path(tmp) / "site")
            parser = Links()
            parser.feed((out / "index.html").read_text(encoding="utf-8"))
            urls = parser.urls + re.findall(r'fetch\("([^"]+)"\)',
                                           (out / "app.js").read_text(encoding="utf-8"))
            self.assertIn("results/leaderboard.json", urls)
            for url in urls:
                parsed = urlsplit(url)
                if parsed.scheme or not parsed.path:
                    continue
                target = (out / parsed.path).resolve()
                self.assertTrue(target.is_relative_to(out), url)
                self.assertTrue(target.is_file(), url)
            self.assertEqual((out / "results/leaderboard.json").read_bytes(),
                             (ROOT / "results/leaderboard.json").read_bytes())
            self.assertEqual((out / "assets/task-atlas.png").read_bytes(),
                             (ROOT / "assets/task-atlas.png").read_bytes())
            self.assertFalse((out / "benchmark").exists())
            with self.assertRaises(FileExistsError):
                build(ROOT, out)
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                build(ROOT, ROOT / "assets" / "export-must-not-be-created")

    def test_module_entrypoint_and_missing_data_are_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT))
            def run(*args):
                return subprocess.run([sys.executable, "-m", "datajevbench", *args],
                                      cwd=tmp, env=env, text=True, capture_output=True)
            self.assertEqual(run("--help").returncode, 0)
            missing = run("verify")
            self.assertEqual(missing.returncode, 2)
            self.assertIn("benchmark/records.jsonl", missing.stderr)
            self.assertIn("benchmark/inputs.jsonl", missing.stderr)
            self.assertNotIn("Traceback", missing.stderr)
            custom = run("verify", "--dataset", "tasks.jsonl", "--inputs", "requests.jsonl")
            self.assertEqual(custom.returncode, 2)
            self.assertIn("tasks.jsonl, requests.jsonl", custom.stderr)
            doctor = run("doctor", "--engine", "datajevbench.engines:create_http",
                         "--engine-options", str(ROOT / "configs/systemone.example.json"),
                         "--model-id", "your-model")
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertEqual(json.loads(doctor.stdout)["network_calls"], 0)


if __name__ == "__main__":
    unittest.main()
