"""Regression: Practice setup panel after groove selector removal."""

from __future__ import annotations

import unittest

from app_ui import practice_setup_summary_text
from practice_state import resolve_practice_groove_style


def _setup_panel_groove_for_summary(session: dict, *, default_groove: str) -> str:
    """Mirror _render_practice_setup_panel groove path (must not use undefined locals)."""
    return resolve_practice_groove_style(session, default_groove=default_groove)


class TestPracticeSetupPanelGrooveHotfix(unittest.TestCase):
    def test_summary_path_no_name_error_and_uses_resolver(self) -> None:
        ss: dict = {
            "instrument": "Piano",
            "level": "Intermediate",
            "focus": "General",
            "practice_minutes": 40,
        }
        groove = _setup_panel_groove_for_summary(ss, default_groove="Ballad")
        self.assertEqual(groove, "Ballad")
        summary = practice_setup_summary_text(
            instrument="Piano",
            level="Intermediate",
            focus="General",
            groove=groove,
            minutes=40,
        )
        self.assertIn("Ballad", summary)

    def test_backing_studio_override_wins_over_song_default(self) -> None:
        ss = {
            "backing_groove_style": "Jazz swing",
            "practice_groove_style": "Pop groove",
        }
        groove = _setup_panel_groove_for_summary(ss, default_groove="Ballad")
        self.assertEqual(groove, "Jazz swing")
        self.assertEqual(ss["practice_groove_style"], "Jazz swing")

    def test_persisted_practice_groove_when_no_backing_override(self) -> None:
        ss = {"practice_groove_style": "Bossa nova"}
        groove = _setup_panel_groove_for_summary(ss, default_groove="Auto")
        self.assertEqual(groove, "Bossa nova")

    def test_practice_setup_panel_has_no_feel_selectbox(self) -> None:
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "streamlit_music_practice_app.py"
        source = path.read_text(encoding="utf-8")
        panel_start = source.find("def _render_practice_setup_panel")
        panel_end = source.find("\ndef _", panel_start + 1)
        panel_src = source[panel_start:panel_end]
        self.assertNotIn('key="practice_groove_style"', panel_src)
        self.assertNotIn("Rhythm / groove feel", panel_src)
        self.assertNotIn('practice_groove_style", _groove)', panel_src)
        self.assertIn("groove=_resolved_groove", panel_src)


class TestGrooveDoesNotSurviveASongSwitch(unittest.TestCase):
    """Reproduces "All the Things You Are shows Pop groove": every cache
    this resolver reads from (backing_groove_style, practice_groove_style,
    the persisted canonical blob) can independently survive a song switch
    through some upstream code path that doesn't invalidate it on that
    exact switch. The one signal that reliably updates on every genuine
    switch is ``_active_song_identity`` -- when it changes, this resolver
    must trust only the caller-supplied authoritative default, not any of
    those caches, regardless of which one is the stale one."""

    def _switch_song(self, ss: dict, *, identity: str, default_groove: str) -> str:
        ss["_active_song_identity"] = identity
        return resolve_practice_groove_style(ss, default_groove=default_groove)

    def test_jazz_standard_does_not_inherit_stale_pop_groove(self) -> None:
        ss = {
            "_active_song_identity": "pk::Pop\x1fSay — John Mayer",
            "backing_groove_style": "Pop groove",
            "practice_groove_style": "Pop groove",
            "practice_state": {"practice_groove_style": "Pop groove"},
        }
        # Prime the tracker as if groove had already been resolved for Say.
        resolve_practice_groove_style(ss, default_groove="Pop groove")
        groove = self._switch_song(
            ss,
            identity="pk::Jazz\x1fAll the Things You Are — Jerome Kern",
            default_groove="Ballad",
        )
        self.assertEqual(groove, "Ballad")

    def test_groove_stays_correct_on_reruns_after_the_switch(self) -> None:
        """The fix must not only work on the render where the switch is
        first detected -- it must hold on every subsequent render of the
        same song too (the actual symptom: it looked briefly right, then
        reverted)."""
        ss = {
            "_active_song_identity": "pk::Pop\x1fSay — John Mayer",
            "backing_groove_style": "Pop groove",
        }
        resolve_practice_groove_style(ss, default_groove="Pop groove")
        self._switch_song(
            ss,
            identity="pk::Jazz\x1fAll the Things You Are — Jerome Kern",
            default_groove="Ballad",
        )
        for _rerun in range(4):
            still = resolve_practice_groove_style(ss, default_groove="Ballad")
            self.assertEqual(still, "Ballad", f"reverted on rerun {_rerun}")

    def test_pop_song_after_a_jazz_song_resolves_its_own_groove(self) -> None:
        """Representative Pop material: the fix must work in both
        directions, not just jazz-after-pop."""
        ss = {
            "_active_song_identity": "pk::Jazz\x1fAll the Things You Are — Jerome Kern",
            "backing_groove_style": "Ballad",
            "practice_groove_style": "Ballad",
        }
        resolve_practice_groove_style(ss, default_groove="Ballad")
        groove = self._switch_song(
            ss,
            identity="pk::Pop\x1fPerfect — Ed Sheeran",
            default_groove="Pop groove",
        )
        self.assertEqual(groove, "Pop groove")

    def test_bossa_jazz_tune_is_not_forced_into_swing(self) -> None:
        """Not every Jazz song is swing -- a bossa/ballad/straight-eighth
        tune must keep its own actual feel."""
        ss = {"_active_song_identity": "pk::Jazz\x1fOld Say"}
        resolve_practice_groove_style(ss, default_groove="Pop groove")
        groove = self._switch_song(
            ss,
            identity="pk::Jazz\x1fBlue Bossa — Kenny Dorham",
            default_groove="Bossa nova",
        )
        self.assertEqual(groove, "Bossa nova")

    def test_manual_backing_override_after_a_switch_still_flows_through(self) -> None:
        """A genuine later user choice on the Backing page must not be
        frozen out by the switch-detection fast path."""
        ss = {"_active_song_identity": "pk::Pop\x1fSay — John Mayer"}
        resolve_practice_groove_style(ss, default_groove="Pop groove")
        self._switch_song(
            ss,
            identity="pk::Jazz\x1fAll the Things You Are — Jerome Kern",
            default_groove="Ballad",
        )
        ss["backing_groove_style"] = "Jazz swing"
        overridden = resolve_practice_groove_style(ss, default_groove="Ballad")
        self.assertEqual(overridden, "Jazz swing")

    def test_same_song_rerender_is_unaffected_by_switch_logic(self) -> None:
        """No _active_song_identity change at all (e.g. identity tracking
        not wired on some page) must fall back to the pre-existing
        cache-priority behavior unchanged."""
        ss = {
            "backing_groove_style": "Jazz swing",
            "practice_groove_style": "Pop groove",
        }
        groove = resolve_practice_groove_style(ss, default_groove="Ballad")
        self.assertEqual(groove, "Jazz swing")


if __name__ == "__main__":
    unittest.main()
