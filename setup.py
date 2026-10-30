"""Include the authoritative release manifest in non-editable installations."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "datajevbench" / "_data"
        target.mkdir(parents=True, exist_ok=True)
        self.copy_file("releases/v0.5/manifest.json", str(target / "manifest.json"))


setup(cmdclass={"build_py": BuildPy})
