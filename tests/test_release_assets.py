"""Check the published release counts and subset illustration."""

from collections import Counter
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class ReleaseAssetsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "releases/v0.5/manifest.json").read_text(encoding="utf-8"))

    def test_task_counts_agree_across_release_metadata(self):
        self.assertEqual(self.manifest["version"], "0.5")
        self.assertEqual(self.manifest["records"], 500)
        self.assertEqual(self.manifest["by_subset"], {"D1": 90, "D2": 90, "D3": 80, "D4": 100, "D5": 80, "D6": 60})
        for field in ("by_subset", "by_type", "by_instruction_language"):
            self.assertEqual(sum(self.manifest[field].values()), self.manifest["records"])
        counts = Counter()
        for source in self.manifest["sources"]:
            self.assertEqual(sum(source["subsets"].values()), source["count"])
            counts.update(source["subsets"])
        self.assertEqual(dict(counts), self.manifest["by_subset"])

    def test_diagram_matches_release_counts_and_readme_size(self):
        root = ET.parse(ROOT / "assets/task-distribution.svg").getroot()
        ns = "{http://www.w3.org/2000/svg}"
        self.assertTrue(root.findtext(f"{ns}title"))
        self.assertTrue(root.findtext(f"{ns}desc"))
        content = " ".join(root.itertext())
        for code, count in self.manifest["by_subset"].items():
            self.assertIn(code, content)
            self.assertIn(f"{count} tasks", content)
        png = (ROOT / "assets/task-atlas.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (3200, 2240))
        for name in ("README.md", "README.zh-CN.md"):
            readme = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn('width="800" height="560"', readme)
            self.assertIn('src="assets/task-atlas.png"', readme)


if __name__ == "__main__":
    unittest.main()
