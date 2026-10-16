"""MC3.4 — the Songs selection flows into Creative; a saved catalog snapshot never chooses the song.

Live failure (6d6c796f): Autumn Leaves → Songs → All of Me → Creative showed Autumn Leaves.
``restore_sbi_active_catalog_identity_before_widgets`` resolved the "Active song" from saved
catalog snapshots, skipping any whose Original Key is C. All of Me *is* in C, so the stale
``catalog_session`` (Autumn Leaves, Bm) won and was written over the explicit pick.
"""

from __future__ import annotations

import ast
import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path

logging.disable(logging.CRITICAL)
ROOT = Path(__file__).resolve().parents[1]
AUTUMN = "Jazz\x1fAutumn Leaves — Jazz Standard"
ALL_OF_ME = "Jazz\x1fAll of Me — Jazz Standard"
IPANEMA = "Jazz\x1fThe Girl from Ipanema — Antonio Carlos Jobim"


def _blob(pick: str, title: str, key: str) -> dict:
    return {
        "pick_key": pick,
        "original_key": key,
        "display_key": key,
        "selected_song": {"pick_key": pick, "title": title, "key": key},
    }


def _saved_failure_state() -> dict:
    """The human's saved shape: Creative's catalog snapshot still on Autumn Leaves (Bm)."""
    autumn = _blob(AUTUMN, "Autumn Leaves", "Bm")
    all_of_me = _blob(ALL_OF_ME, "All of Me", "C")
    return {
        "active_music_source": "catalog_song",
        "explicit_music_source_choice": "catalog_song",
        "sbi_preview_source": "Active song",
        "improv_song_source": "Active song",
        "catalog_session": dict(autumn),
        "_catalog_before_custom_state": dict(all_of_me),
        "_last_catalog_song_state": dict(all_of_me),
        "creative_workspace_state": {"catalog_session": dict(autumn)},
        "catalog_recent_pick_keys": [ALL_OF_ME, AUTUMN, IPANEMA],
    }


def _select(session: dict, pick: str, title: str) -> None:
    """What the explicit Songs selection commits (the canonical song keys)."""
    session["active_catalog_pick_key"] = pick
    session["song"] = title
    session["selected_song"] = {"pick_key": pick, "title": title}


class TestSavedCatalogSnapshotNeverChoosesTheSong(unittest.TestCase):
    def test_all_of_me_survives_the_stale_autumn_catalog_snapshot(self) -> None:
        from source_session_state import restore_sbi_active_catalog_identity_before_widgets

        s = _saved_failure_state()
        _select(s, ALL_OF_ME, "All of Me")
        restore_sbi_active_catalog_identity_before_widgets(s)  # the Creative-entry pre-widget restore
        self.assertEqual(s["active_catalog_pick_key"], ALL_OF_ME)
        self.assertEqual(s["song"], "All of Me")
        self.assertEqual(s["catalog_session"]["pick_key"], ALL_OF_ME)  # the snapshot follows the song
        self.assertEqual(s["catalog_session"]["original_key"].split()[0], "C")  # not Autumn's Bm

    def test_resolver_returns_the_live_pick_and_its_own_original_key(self) -> None:
        from source_session_state import resolve_sbi_active_catalog_identity

        s = _saved_failure_state()
        _select(s, ALL_OF_ME, "All of Me")
        pick, sel, orig = resolve_sbi_active_catalog_identity(s)
        self.assertEqual(pick, ALL_OF_ME)
        self.assertEqual(sel.get("pick_key"), ALL_OF_ME)
        self.assertNotEqual(orig.split()[0] if orig else "", "Bm")

    def test_the_other_direction_and_a_second_switch(self) -> None:
        from source_session_state import restore_sbi_active_catalog_identity_before_widgets

        s = _saved_failure_state()
        s["catalog_session"] = _blob(ALL_OF_ME, "All of Me", "C")
        _select(s, AUTUMN, "Autumn Leaves")
        restore_sbi_active_catalog_identity_before_widgets(s)
        self.assertEqual(s["active_catalog_pick_key"], AUTUMN)
        _select(s, IPANEMA, "The Girl from Ipanema")
        restore_sbi_active_catalog_identity_before_widgets(s)
        self.assertEqual(s["active_catalog_pick_key"], IPANEMA)
        self.assertEqual(s["song"], "The Girl from Ipanema")

    def test_snapshot_still_restores_the_catalog_song_when_none_is_live(self) -> None:
        # Leaving Custom for "Active song": no Catalog pick is live, so the saved
        # catalog snapshot is the only record of the song to return to (unchanged).
        from source_session_state import resolve_sbi_active_catalog_identity

        s = _saved_failure_state()
        s["active_catalog_pick_key"] = "custom::trial-d"
        pick, _sel, orig = resolve_sbi_active_catalog_identity(s)
        self.assertEqual(pick, AUTUMN)
        self.assertEqual(orig, "Bm")

    def test_original_key_is_never_borrowed_from_another_song(self) -> None:
        from source_session_state import resolve_sbi_active_catalog_identity

        s = {
            "active_music_source": "catalog_song",
            "catalog_session": _blob(AUTUMN, "Autumn Leaves", "Bm"),
            "_last_catalog_song_state": _blob(IPANEMA, "The Girl from Ipanema", "F"),
        }
        _select(s, ALL_OF_ME, "All of Me")
        _pick, _sel, orig = resolve_sbi_active_catalog_identity(s)
        self.assertNotIn(orig.split()[0] if orig else "", {"Bm", "F"})


class TestMissionBackingOpenedFromLabel(unittest.TestCase):
    """'Opened from Missions' on Mission Backing; 'Practice' only for real Practice handoffs."""

    @staticmethod
    def _origin(session: dict) -> str:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        node = next(
            n for n in ast.parse(src).body
            if isinstance(n, ast.FunctionDef) and n.name == "_backing_scope_handoff_origin"
        )

        class _St:
            session_state = session

        ns: dict = {"st": _St}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "origin", "exec"), ns)
        return ns["_backing_scope_handoff_origin"]()

    def test_mission_backing_says_missions(self) -> None:
        self.assertEqual(self._origin({"backing_context": {"source": "mission", "active_song_id": AUTUMN}}), "Missions")

    def test_practice_and_other_backing_keep_practice(self) -> None:
        self.assertEqual(self._origin({"backing_context": {"source": "regular_song", "active_song_id": AUTUMN}}), "Practice")
        self.assertEqual(self._origin({}), "Practice")

    def test_the_label_uses_the_origin(self) -> None:
        src = (ROOT / "streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("Opened from <strong>{_backing_scope_handoff_origin()}</strong>", src)
        self.assertNotIn("Opened from <strong>Practice</strong>", src)


class TestAutumnToAllOfMeApp(unittest.TestCase):
    """Real app: Autumn Leaves (Creative visited) → Songs → All of Me → Creative stays All of Me."""

    def test_all_of_me_stays_active_in_creative(self) -> None:
        from streamlit.testing.v1 import AppTest

        data_dir = tempfile.mkdtemp(prefix="mc34_switch_")
        prior = os.environ.get("MUSIC_APP_DATA_DIR")
        os.environ["MUSIC_APP_DATA_DIR"] = data_dir
        try:
            at = AppTest.from_file(str(ROOT / "streamlit_music_practice_app.py"), default_timeout=300)
            at.run(timeout=300)

            def click(key):
                btn = next((w for w in at.button if str(w.key) == key), None)
                if btn is None and key == "studio_quick_nav_btn_picker":
                    btn = next((w for w in at.button if str(w.key) == "sidebar_goto_song_selection"), None)
                self.assertIsNotNone(btn, (key, [str(e.value)[:300] for e in at.exception]))
                btn.click()
                at.run(timeout=300)

            def pick(needle):
                dd = at.selectbox(key="matching_song_dropdown")
                dd.set_value([o for o in dd.options if needle in o][0])
                at.run(timeout=300)

            def assert_on(pick_key, title):
                ss = at.session_state
                self.assertEqual(ss["active_catalog_pick_key"], pick_key)
                self.assertEqual(ss["song"], title)
                self.assertNotIn("_music_workflow_activation_error", ss)
                text = " ".join(str(m.value) for m in list(at.markdown) + list(at.info) + list(at.caption))
                other = {"Autumn Leaves", "All of Me", "The Girl from Ipanema"} - {title}
                self.assertFalse([o for o in other if f"tied to **{o}**" in text or f"coach for {o}" in text], text[:400])

            click("studio_quick_nav_btn_picker")
            pick("Autumn Leaves — Jazz Standard")
            click("studio_quick_nav_btn_creative")  # Creative visited on Autumn Leaves (writes its catalog snapshot)
            assert_on(AUTUMN, "Autumn Leaves")
            click("studio_quick_nav_btn_picker")
            pick("All of Me — Jazz Standard")
            self.assertEqual(at.session_state["active_catalog_pick_key"], ALL_OF_ME)
            click("studio_quick_nav_btn_creative")
            assert_on(ALL_OF_ME, "All of Me")
            click("studio_quick_nav_btn_picker")
            pick("The Girl from Ipanema")
            click("studio_quick_nav_btn_creative")
            assert_on(IPANEMA, "The Girl from Ipanema")
        finally:
            if prior is None:
                os.environ.pop("MUSIC_APP_DATA_DIR", None)
            else:
                os.environ["MUSIC_APP_DATA_DIR"] = prior
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
