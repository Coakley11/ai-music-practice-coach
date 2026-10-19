"""Key Cycling Off retires every cycle element; the lead-sheet hand-off resumes
only the page player.

CROSSAUDIO4: after Off, the player cleared only the two elements then named
kc-buf-0/1. Key switches swap element ids, so takes stayed loaded under
kc-park-* / kc-prep-* ids. Opening the Lead Sheet recorded a playhead hand-off,
and the transport's applyHandoff resumed any paused page audio of the same
length -- the leftover kc-park-A -- instead of the sheet.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_KC = (_ROOT / "backing_key_cycle.py").read_text(encoding="utf-8")
_TRANSPORT = (_ROOT / "backing_transport_component" / "index.html").read_text(encoding="utf-8")


def _js_function(src: str, name: str) -> str:
    m = re.search(r"function " + re.escape(name) + r"\(.*?\n    \}\}\n", src, re.S)
    assert m, f"{name} not found"
    return m.group(0)


class OffTeardownContractTests(unittest.TestCase):
    def test_off_retires_every_key_cycle_element(self) -> None:
        off = _KC[_KC.index("if (!cmd.enabled) {{"):]
        off = off[: off.index("return;")]
        self.assertIn("retireAllKcElements();", off)
        retire = _js_function(_KC, "retireAllKcElements")
        for sel in ('audio[id^="kc-"]', "audio[data-kc-park]", "audio[data-kc-prep]"):
            self.assertIn(sel, retire)
        element = _js_function(_KC, "retireKcElement")
        for step in ("pause()", "removeAttribute('src')", "removeAttribute('data-kc-url')", "load()"):
            self.assertIn(step, element)

    def test_parked_and_prepared_elements_follow_the_server_live_set(self) -> None:
        self.assertIn('"liveUrls":', _KC)
        note = _js_function(_KC, "noteCmdNeighbors")
        self.assertIn("retireUnlistedParked()", note)
        for fn in ("parkKey", "ensureDecoded"):
            self.assertIn("kcUrlIsLive(url)", _js_function(_KC, fn))


class HandoffTargetContractTests(unittest.TestCase):
    def test_handoff_resumes_only_the_page_player(self) -> None:
        apply = _TRANSPORT[_TRANSPORT.index("function applyHandoff()"):]
        apply = apply[: apply.index("function anyEnded()")]
        self.assertIn("isPagePlayer(a)", apply)
        self.assertIn('[data-testid="stAudio"]', _TRANSPORT[_TRANSPORT.index("function isPagePlayer"):])


if __name__ == "__main__":
    unittest.main()
