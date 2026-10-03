"""R4 — Custom identity / key / material across Creative workflows (X1-X8).

Pure session-state-dict tests calling real production functions directly
(no Streamlit/browser), matching the established R1/R2/R3 test convention.

Trial Song scenario used throughout: Custom song, Original Key E minor,
canonical progression Em - Em - D - D, Practice Key C minor, so the
correctly-projected progression is Cm - Cm - Bb - Bb (verified both by music
theory and by running the app's real transpose function).
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import build_custom_progression_context
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    default_active_progression,
    sync_custom_workspace_practice_key,
)
from improvisation_intelligence_ui import (
    _authoritative_concert_sections,
    _authoritative_practice_chart_key,
)
from songs.music_source import SOURCE_CATALOG, commit_custom_active_song
from songs.practice_key_state import get_practice_concert_key
from source_session_state import sync_catalog_session


def _trial_song_session_with_stale_catalog() -> dict:
    """Realistic prior Catalog visit (Shape of You, Bm) + Trial Song activated
    as Global Active via the real commit path, Practice Key set to C minor."""
    session: dict = {
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": "Pop\x1fShape of You",
        "song": "Shape of You",
        "display_key": "Bm",
        "concert_key": "Bm",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": "Pop\x1fShape of You",
        },
        "practice_key_by_source": {"Pop\x1fShape of You": "Bm"},
    }
    sync_catalog_session(session)
    active = default_active_progression()
    active["id"] = "trial-1"
    active["name"] = "Trial Song"
    active["original_key_center"] = "Em"
    active["user_locked_home_key"] = True
    active["original_sections"]["Verse"] = [
        {"chord": "Em", "bars": 1},
        {"chord": "Em", "bars": 1},
        {"chord": "D", "bars": 1},
        {"chord": "D", "bars": 1},
    ]
    session[CPL_ACTIVE_KEY] = active
    st = SimpleNamespace(session_state=session)
    commit_custom_active_song(st, active, invalidate_backing=lambda *a, **k: None)
    sync_custom_workspace_practice_key(session, practice_key="Cm", active=active)
    return session


def _assert_canonical_intact(test: unittest.TestCase, session: dict) -> None:
    active = session[CPL_ACTIVE_KEY]
    test.assertEqual(active.get("original_key_center"), "Em")
    test.assertEqual(
        [e.get("chord") for e in active["original_sections"]["Verse"]],
        ["Em", "Em", "D", "D"],
    )


class TestX1CustomToSBI(unittest.TestCase):
    def test_sbi_preview_shows_trial_song_not_stale_catalog(self) -> None:
        """Regression: SBI with default 'Active song' source (no explicit radio
        click) must follow real Global Active (Custom), not a never-invalidated
        stale catalog_session bucket from a Catalog song viewed earlier."""
        from source_session_state import resolve_sbi_preview

        session = _trial_song_session_with_stale_catalog()
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Trial Song")
        self.assertEqual(preview["display_key"], "Cm")
        self.assertEqual(preview["original_key"], "Em")
        self.assertEqual(preview["sections"].get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)

    def test_sbi_return_leaves_custom_unchanged(self) -> None:
        from source_session_state import resolve_sbi_preview

        session = _trial_song_session_with_stale_catalog()
        resolve_sbi_preview(session)
        _assert_canonical_intact(self, session)
        pick = session[CPL_ACTIVE_KEY].get("id")
        self.assertEqual(get_practice_concert_key(session, f"custom::{pick}"), "Cm")


class TestX2CustomToMissions(unittest.TestCase):
    def test_missions_derives_from_correct_custom_context(self) -> None:
        session = _trial_song_session_with_stale_catalog()
        session["improv_intelligence_tab"] = "Missions"
        key = _authoritative_practice_chart_key(session, "FALLBACK")
        sections = _authoritative_concert_sections(session, {})
        self.assertEqual(key, "Cm")
        self.assertEqual(sections.get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)


class TestX3CustomToLiveCoach(unittest.TestCase):
    def test_live_coach_key_and_return(self) -> None:
        """Regression: Live Coach (and the shared tab-key resolver) used to
        route 'Active song' straight into a Catalog-only resolver
        (_sbi_active_canonical_practice_key) regardless of whether Custom was
        genuinely Global Active, producing the literal fallback value instead
        of the real Custom Practice Key."""
        session = _trial_song_session_with_stale_catalog()
        session["improv_intelligence_tab"] = "Live Coach"
        key = _authoritative_practice_chart_key(session, "FALLBACK")
        self.assertEqual(key, "Cm")
        self.assertNotEqual(key, "FALLBACK")
        _assert_canonical_intact(self, session)


class TestX4CustomToHarmonyMap(unittest.TestCase):
    def test_harmony_map_reflects_active_custom_without_mutating_canonical(self) -> None:
        session = _trial_song_session_with_stale_catalog()
        session["improv_intelligence_tab"] = "Harmony Map"
        key = _authoritative_practice_chart_key(session, "FALLBACK")
        sections = _authoritative_concert_sections(session, {})
        self.assertEqual(key, "Cm")
        self.assertEqual(sections.get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)


class TestX5CustomToMotif(unittest.TestCase):
    def test_motif_uses_practice_projection_not_stale_catalog(self) -> None:
        session = _trial_song_session_with_stale_catalog()
        session["improv_intelligence_tab"] = "Phrase / Motif"
        key = _authoritative_practice_chart_key(session, "FALLBACK")
        sections = _authoritative_concert_sections(session, {})
        self.assertEqual(key, "Cm")
        self.assertEqual(sections.get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)


class TestX6CustomToBacking(unittest.TestCase):
    def test_backing_owns_trial_song_after_visiting_another_tool(self) -> None:
        session = _trial_song_session_with_stale_catalog()
        session["improv_intelligence_tab"] = "Harmony Map"
        _authoritative_practice_chart_key(session, "FB")
        _authoritative_concert_sections(session, {})

        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.song_title, "Trial Song")
        self.assertEqual(ctx.concert_key, "Cm")
        self.assertEqual(ctx.progression, ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)


class TestX7MultiHopJourney(unittest.TestCase):
    def test_custom_sbi_mission_live_coach_backing_chain(self) -> None:
        """Custom -> SBI -> Mission -> Live Coach -> Backing -> final state
        must still be Trial Song, Original Em, Practice Cm, canonical
        Em-Em-D-D, projected Cm-Cm-Bb-Bb at every boundary."""
        from source_session_state import resolve_sbi_preview

        session = _trial_song_session_with_stale_catalog()

        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Trial Song")
        self.assertEqual(preview["sections"].get("Verse"), ["Cm", "Cm", "Bb", "Bb"])

        session["improv_intelligence_tab"] = "Missions"
        self.assertEqual(_authoritative_practice_chart_key(session, "FB"), "Cm")

        session["improv_intelligence_tab"] = "Live Coach"
        self.assertEqual(_authoritative_practice_chart_key(session, "FB"), "Cm")

        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.source, "custom_progression")
        self.assertEqual(ctx.concert_key, "Cm")
        self.assertEqual(ctx.progression, ["Cm", "Cm", "Bb", "Bb"])
        self.assertEqual(ctx.song_title, "Trial Song")

        _assert_canonical_intact(self, session)
        pick = session[CPL_ACTIVE_KEY].get("id")
        self.assertEqual(get_practice_concert_key(session, f"custom::{pick}"), "Cm")


class TestX8StaleCatalogIsolation(unittest.TestCase):
    """Every test above already seeds a realistic stale Catalog visit
    (_trial_song_session_with_stale_catalog); this class adds an explicit,
    dedicated assertion that the stale bucket itself is never mutated/cleared
    merely by Creative navigation (only an explicit Catalog pick may do so)."""

    def test_stale_catalog_session_untouched_by_creative_navigation(self) -> None:
        session = _trial_song_session_with_stale_catalog()
        stale_before = dict(session.get("catalog_session") or {})
        for tab in ("Missions", "Live Coach", "Harmony Map", "Phrase / Motif"):
            session["improv_intelligence_tab"] = tab
            _authoritative_practice_chart_key(session, "FB")
            _authoritative_concert_sections(session, {})
        build_custom_progression_context(session)
        self.assertEqual(session.get("catalog_session"), stale_before)
        _assert_canonical_intact(self, session)

    def test_no_creative_view_substitutes_stale_catalog_identity(self) -> None:
        from source_session_state import resolve_sbi_preview

        session = _trial_song_session_with_stale_catalog()
        for tab in ("Missions", "Live Coach", "Harmony Map", "Phrase / Motif"):
            session["improv_intelligence_tab"] = tab
            key = _authoritative_practice_chart_key(session, "FB")
            self.assertNotEqual(key, "Bm", f"tab={tab} leaked stale Catalog key")
        preview = resolve_sbi_preview(session)
        self.assertNotEqual(preview["title"], "Shape of You")
        self.assertNotEqual(preview["display_key"], "Bm")


if __name__ == "__main__":
    unittest.main()
