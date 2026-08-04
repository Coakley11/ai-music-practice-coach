"""Fail when production modules write authoritative workflow keys directly."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED_FILES = {
    "music_workflow_activation.py",
    "music_workflow_mutation.py",
    "music_workflow_state_store.py",
    "music_workflow_legacy_projection.py",
    "music_workflow_canonical_persistence.py",
    "music_workflow_guard.py",
}

FORBIDDEN_PATTERNS = (
    re.compile(r'session\s*\[\s*["\']_music_active_workflow["\']\s*\]\s*='),
    re.compile(r'session\s*\[\s*["\']_active_workflow_owner["\']\s*\]\s*='),
)


class TestUnauthorizedDirectWorkflowWrites(unittest.TestCase):
    def test_production_modules_do_not_assign_authoritative_keys(self) -> None:
        violations: list[str] = []
        for path in ROOT.glob("*.py"):
            if path.name.startswith("test_") or path.name in ALLOWED_FILES:
                continue
            if path.name.startswith("music_workflow_") and path.name not in ALLOWED_FILES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in FORBIDDEN_PATTERNS:
                if pat.search(text):
                    violations.append(f"{path.name}: {pat.pattern}")
        self.assertEqual(violations, [], msg="Direct authoritative writes: " + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()
