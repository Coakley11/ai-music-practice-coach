"""One-off: extract coach overlay helpers from main app."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src_lines = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8").splitlines(keepends=True)

header = '''"""Practice coach overlay text for chord sections (no Streamlit UI)."""

from __future__ import annotations

import html

__all__ = ["section_overlay_html"]


'''

ranges = [
    (1485, 1501),
    (1593, 1660),
    (2686, 2697),
    (2792, 2806),
    (3626, 3642),
    (2894, 3040),
]
chunks = []
for a, b in ranges:
    chunks.append("".join(src_lines[a - 1 : b]))

body = header + "\n".join(chunks)
body = body.replace("def _section_overlay(", "def section_overlay_html(")
(ROOT / "coach_overlay.py").write_text(body, encoding="utf-8")
print("Wrote coach_overlay.py")
