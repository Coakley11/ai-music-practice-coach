"""Voice is an instrument, not Karaoke: Mission Backing never shows Karaoke session or lyrics UI.

Also guards the Mission-Backing suppression flags: ordinary Mission playback, Practice Key changes and
Missions <-> Backing navigation must not set them (a set flag hides the example and, before this fix,
let the Voice instrument turn Mission Backing into a Karaoke page).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any

from backing_session_route import (
    deactivate_mission_backing_ui_state,
    is_mission_backing_context,
    mission_backing_ui_allowed,
    on_creative_backing_handoff,
)
from improvisation_missions import MISSION_EXAMPLE_KEY, MISSION_PRACTICE_LICK_KEY, transpose_stored_mission_example

APP = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
FLAGS = ("_backing_mission_ui_suppressed", "_pending_upload_suppresses_mission_backing")


def _mission_session(source: str = "mission") -> dict[str, Any]:
    return {
        MISSION_PRACTICE_LICK_KEY: {"motif": {"notes": ["C"]}, "song_title": "Shallow"},
        "backing_context": {"source": source, "source_label": "Mission Practice", "bpm": 100, "groove": "Pop groove",
                            "style": "Pop", "meter": "4/4", "progression": ["G"], "progression_label": "G"},
        "instrument": "Voice",
    }


class TestContextPredicate(unittest.TestCase):
    def test_mission_context_is_true_for_a_mission_and_false_otherwise(self) -> None:
        self.assertTrue(is_mission_backing_context(_mission_session("mission")))
        for src in ("entry_jam", "song_improv", "custom_progression", "catalog"):
            self.assertFalse(is_mission_backing_context(_mission_session(src)), src)
        self.assertFalse(is_mission_backing_context({}))

    def test_a_suppressed_example_is_still_a_mission_context(self) -> None:
        s = _mission_session()
        deactivate_mission_backing_ui_state(s)
        self.assertFalse(mission_backing_ui_allowed(s))          # example hidden
        self.assertTrue(is_mission_backing_context(s))           # ...but the page is still a Mission page
        s["_pending_upload_suppresses_mission_backing"] = True
        self.assertTrue(is_mission_backing_context(s))

    def test_regular_backing_is_not_a_mission_context(self) -> None:
        s = _mission_session("catalog")
        on_creative_backing_handoff(s, source="entry_jam")
        self.assertFalse(is_mission_backing_context(s))


class TestKaraokeUiIsGatedOnTheMissionContext(unittest.TestCase):
    def setUp(self) -> None:
        self.src = APP.read_text(encoding="utf-8")

    def test_every_karaoke_block_on_the_backing_page_checks_the_mission_context(self) -> None:
        i = self.src.index("_mission_backing_ctx = _is_mission_backing_ctx(")
        block = self.src[i:i + 6000]
        self.assertRegex(block, r"_karaoke_session_ui = \(\s*km\.is_voice_mode\(st\.session_state\)\s*and km\.is_karaoke_session_active\(st\.session_state\)\s*and not _mission_backing_ctx")
        self.assertIn("if not _mission_backing_ctx and (_karaoke_session_ui or km.is_voice_mode(st.session_state)):", block)
        self.assertIn("if not _mission_backing_ctx and not km.is_karaoke_session_active(st.session_state):\n"
                      "        render_karaoke_missing_lyrics_cta(", block.replace("\r\n", "\n"))
        self.assertIn("if not _mission_backing_ctx and km.is_karaoke_session_active(st.session_state):\n"
                      "        render_karaoke_setlist_missing_lyrics_cta(", self.src.replace("\r\n", "\n"))

    def test_the_gate_does_not_depend_on_the_example_being_visible(self) -> None:
        i = self.src.index("_mission_backing_ctx = _is_mission_backing_ctx(")
        self.assertNotIn("mission_backing_ui_allowed", self.src[i - 400:i + 600])

    def test_karaoke_is_not_disabled_globally_for_voice(self) -> None:
        # explicit Karaoke sessions and non-Mission Backing still render the expander
        self.assertRegex(self.src, r"if not _mission_backing_ctx and \(_karaoke_session_ui or km\.is_voice_mode")
        self.assertGreater(len(re.findall(r"render_karaoke_skip_controls\(", self.src)), 0)


class TestNormalMissionFlowNeverSuppresses(unittest.TestCase):
    def test_practice_key_changes_do_not_set_suppression_flags(self) -> None:
        from improvisation_intelligence_ui import _run_mission_example_generate
        from tests.test_mission_example_canonical_transposition import _session

        s = _session("Voice")
        _run_mission_example_generate(s, "normal")
        s.update(_mission_session())
        cur = "G"
        for k in ("A", "Bb", "G"):
            transpose_stored_mission_example(s, from_key=cur, to_key=k)
            cur = k
            for f in FLAGS:
                self.assertFalse(s.get(f), (k, f))
            self.assertTrue(isinstance(s.get(MISSION_EXAMPLE_KEY), dict))
            self.assertTrue(mission_backing_ui_allowed(s))

    def test_mission_handoff_clears_rather_than_sets_suppression(self) -> None:
        s = _mission_session()
        s["_backing_mission_ui_suppressed"] = True
        on_creative_backing_handoff(s, source="mission")
        self.assertFalse(s.get("_backing_mission_ui_suppressed"))
        self.assertTrue(mission_backing_ui_allowed(s))

    def test_only_regular_backing_routes_set_the_flag(self) -> None:
        root = APP.parent
        setters = []
        for p in root.glob("*.py"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r'\[\s*"(_backing_mission_ui_suppressed|_pending_upload_suppresses_mission_backing)"\s*\]\s*=\s*True', t):
                setters.append(p.name)
        self.assertEqual(sorted(setters), ["backing_session_route.py", "pending_upload_route_precedence.py"])


if __name__ == "__main__":
    unittest.main()
