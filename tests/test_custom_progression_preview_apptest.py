"""AppTest: Custom Progressions Preview Section / Preview Entire Song (headless, no browser)."""

from __future__ import annotations

import copy
import os
import re
import tempfile
import unittest

os.environ.setdefault("MUSIC_APP_DATA_DIR", tempfile.mkdtemp(prefix="cpl_preview_apptest_"))

from streamlit.testing.v1 import AppTest

from custom_progression_lab import CPL_ACTIVE_KEY, CPL_SAVED_KEY
from custom_progression_preview import PREVIEW_STATE_KEY


def _page() -> None:
    from cpl_page_ui import render_custom_progression_lab_page

    render_custom_progression_lab_page()


def _song() -> dict:
    return {
        "name": "Preview Test Song",
        "original_key_center": "C",
        "original_sections": {
            "Intro": [],
            "Verse": [
                {"chord": "C:2|F:2", "bars": 1},
                {"chord": "Am", "bars": 1},
                {"chord": "G", "bars": 2},
            ],
            "Pre-Chorus": [],
            "Chorus": [{"chord": "F", "bars": 1}, {"chord": "G", "bars": 1}],
            "Bridge": [],
            "Solo": [],
            "Outro": [],
        },
        "progression_style": "Pop",
        "user_locked_home_key": True,
        "time_signature": "4/4",
        "bpm": 100,
        "groove_style": "Auto",
        "loops": 2,
    }


def _restore_real_components_html() -> None:
    """Earlier AppTest harnesses replace streamlit.components.v1.html in-process and never restore it;
    these tests count the real iframes the player mounts, so start from the real function."""
    import importlib

    import streamlit.components.v1 as _components

    importlib.reload(_components)


def _boot(song: dict | None = None) -> AppTest:
    _restore_real_components_html()
    at = AppTest.from_function(_page, default_timeout=180)
    at.session_state[CPL_ACTIVE_KEY] = copy.deepcopy(song or _song())
    at.session_state["cpl_edit_section"] = "Verse"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _frames(at: AppTest) -> list[str]:
    out = []
    for el in at.get("iframe"):
        src = getattr(el.proto, "srcdoc", "") or ""
        if "cplay-wrap" in src:
            out.append(src)
    return out


def _identity(at: AppTest) -> dict:
    keep = (
        "cpl_active_progression",
        "cpl_saved_progressions",
        "active_catalog_pick_key",
        "active_song_id",
        "active_music_source",
        "music_source",
    )
    snap = {k: copy.deepcopy(at.session_state[k]) for k in keep if k in at.session_state}
    snap[CPL_ACTIVE_KEY] = copy.deepcopy(at.session_state[CPL_ACTIVE_KEY])
    snap[CPL_SAVED_KEY] = copy.deepcopy(at.session_state[CPL_SAVED_KEY])
    return snap


def _chips(html: str) -> list[str]:
    return re.findall(r'<span class="cplay-chip-sym">([^<]*)</span>', html)


class TestPreviewSection(unittest.TestCase):
    def test_buttons_present_and_nothing_mounted_before_click(self):
        at = _boot()
        self.assertIn("cpl_preview_section_Verse", [b.key for b in at.button])
        self.assertIn("cpl_preview_song", [b.key for b in at.button])
        self.assertEqual(_frames(at), [])
        self.assertNotIn(PREVIEW_STATE_KEY, at.session_state)

    def test_preview_section_mounts_player_in_entered_order_with_split(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        self.assertFalse(at.exception)
        frames = _frames(at)
        self.assertEqual(len(frames), 1)
        self.assertEqual(_chips(frames[0]), ["C", "F", "Am", "G"])
        self.assertIn("Verse preview", frames[0])
        for needle in ("Pause", "Resume", "&#9632; Stop", "resetAll", "cplprev-section-1"):
            self.assertIn(needle, frames[0])

    def test_preview_does_not_change_saved_data_or_active_identity(self):
        at = _boot()
        before = _identity(at)
        at.button(key="cpl_preview_section_Verse").click().run()
        at.button(key="cpl_preview_song").click().run()
        at.button(key="cpl_preview_section_Verse").click().run()
        after = _identity(at)
        self.assertEqual(before, after)

    def test_replay_after_stop_rearms_with_new_player_instance(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        first = _frames(at)[0]
        # Pause / Resume / Stop run inside the player (no Streamlit rerun, state unchanged).
        at.run()
        self.assertEqual(_frames(at)[0], first)
        at.button(key="cpl_preview_section_Verse").click().run()
        second = _frames(at)[0]
        self.assertIn("cplprev-section-2", second)
        self.assertNotEqual(first, second)

    def test_unsaved_edit_is_audible_in_next_preview(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        old_audio = re.search(r"base64,([A-Za-z0-9+/=]+)", _frames(at)[0]).group(1)
        # Unsaved draft edit: append Dm to the Verse via the builder buttons.
        at.button(key="cpl_pick_Verse_Dm").click().run() if "cpl_pick_Verse_Dm" in [b.key for b in at.button] else None
        active = copy.deepcopy(at.session_state[CPL_ACTIVE_KEY])
        active["original_sections"]["Verse"].append({"chord": "Dm", "bars": 1})
        at.session_state[CPL_ACTIVE_KEY] = active
        at.run()
        self.assertEqual(_frames(at), [])  # stale preview is unmounted on edit
        at.button(key="cpl_preview_section_Verse").click().run()
        frame = _frames(at)[0]
        self.assertEqual(_chips(frame)[-1], "Dm")
        self.assertNotEqual(old_audio, re.search(r"base64,([A-Za-z0-9+/=]+)", frame).group(1))
        self.assertNotIn("Dm", str(copy.deepcopy(at.session_state[CPL_SAVED_KEY])))

    def test_switching_section_resets_player(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        self.assertEqual(len(_frames(at)), 1)
        at.selectbox(key="cpl_edit_section").select("Chorus").run()
        self.assertFalse(at.exception)
        self.assertEqual(_frames(at), [])
        self.assertNotIn(PREVIEW_STATE_KEY, at.session_state)
        at.selectbox(key="cpl_edit_section").select("Verse").run()
        self.assertEqual(_frames(at), [])  # does not resurrect

    def test_empty_section_button_disabled(self):
        at = _boot()
        at.selectbox(key="cpl_edit_section").select("Bridge").run()
        btn = next(b for b in at.button if b.key == "cpl_preview_section_Bridge")
        self.assertTrue(btn.disabled)

    def test_tempo_edit_invalidates_preview(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        self.assertEqual(len(_frames(at)), 1)
        at.slider(key="cpl_bpm_builder").set_value(140).run()
        self.assertEqual(_frames(at), [])
        at.button(key="cpl_preview_section_Verse").click().run()
        self.assertIn("140 BPM", _frames(at)[0])


class TestPreviewSong(unittest.TestCase):
    def test_song_preview_uses_actual_order_and_headers(self):
        at = _boot()
        at.button(key="cpl_preview_song").click().run()
        self.assertFalse(at.exception)
        frames = _frames(at)
        self.assertEqual(len(frames), 1)
        heads = re.findall(r'class="cplay-sec" data-sec="\d+">([^<]+)<', frames[0])
        self.assertEqual(heads, ["Verse", "Chorus"])
        self.assertEqual(_chips(frames[0]), ["C", "F", "Am", "G", "F", "G"])
        # the order and its source are visible, and the default is not passed off as the user's structure
        notes = [str(c.value) for c in at.caption if "default order" in str(c.value)]
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("Verse → Chorus", notes[0])
        self.assertIn("not your song structure", notes[0])
        self.assertIn("Entire song preview", frames[0])
        self.assertIn("cplay-now", frames[0])

    def test_song_preview_replaces_section_preview_and_section_reset_does_not_kill_song(self):
        at = _boot()
        at.button(key="cpl_preview_section_Verse").click().run()
        at.button(key="cpl_preview_song").click().run()
        frames = _frames(at)
        self.assertEqual(len(frames), 1)
        self.assertIn("Entire song preview", frames[0])
        at.selectbox(key="cpl_edit_section").select("Chorus").run()
        self.assertEqual(len(_frames(at)), 1)  # a song preview is not tied to the edited section

    def test_song_preview_follows_unsaved_edit_by_resetting(self):
        at = _boot()
        at.button(key="cpl_preview_song").click().run()
        active = copy.deepcopy(at.session_state[CPL_ACTIVE_KEY])
        active["original_sections"]["Chorus"].append({"chord": "C", "bars": 1})
        at.session_state[CPL_ACTIVE_KEY] = active
        at.run()
        self.assertEqual(_frames(at), [])
        at.button(key="cpl_preview_song").click().run()
        self.assertEqual(_chips(_frames(at)[0]).count("C"), 1 + 1)

    def test_song_button_disabled_without_chords(self):
        blank = _song()
        for k in blank["original_sections"]:
            blank["original_sections"][k] = []
        at = _boot(blank)
        btn = next(b for b in at.button if b.key == "cpl_preview_song")
        self.assertTrue(btn.disabled)


if __name__ == "__main__":
    unittest.main()
