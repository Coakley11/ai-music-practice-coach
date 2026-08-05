"""Requirements/runtime pins for Streamlit Cloud Python 3.12 + audio stack."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


class TestRequirementsPythonStack(unittest.TestCase):
    def test_runtime_pins_python_312(self) -> None:
        runtime = (Path(__file__).resolve().parents[1] / "runtime.txt").read_text(encoding="utf-8")
        self.assertRegex(runtime.strip(), r"python-3\.12")

    def test_python_version_file_matches_runtime(self) -> None:
        root = Path(__file__).resolve().parents[1]
        runtime = (root / "runtime.txt").read_text(encoding="utf-8").strip()
        pyver = (root / ".python-version").read_text(encoding="utf-8").strip()
        m = re.search(r"python-(3\.\d+\.\d+)", runtime)
        self.assertIsNotNone(m)
        assert m is not None
        self.assertTrue(pyver.startswith(m.group(1).rsplit(".", 1)[0]))

    def test_requirements_pin_modern_numba_llvmlite(self) -> None:
        req = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
        self.assertRegex(req, r"numba>=0\.5[89]")
        self.assertRegex(req, r"llvmlite>=0\.42")
        self.assertIn("librosa>=0.10", req)
        self.assertNotIn("numba==0.53", req)
        self.assertNotIn("llvmlite==0.36", req)

    def test_no_stale_numba_pins_anywhere(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for path in (root / "requirements.txt",):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"numba==0\.53")
            self.assertNotRegex(text, r"llvmlite==0\.36")


if __name__ == "__main__":
    unittest.main()
