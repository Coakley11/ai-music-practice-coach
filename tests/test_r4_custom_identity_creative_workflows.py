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


class TestLiveStoredActiveIsNotLeaveCustom(unittest.TestCase):
    """Live Motif/Backing leak: leftover stored 'Active song' + leftover display_key Bm.

    The accepted R4 unit path never stamped improv_song_source / sbi_preview_source,
    so it never reached the Catalog-only Motif branch. Live Creative does.
    """

    def _live_stamps(self, session: dict) -> dict:
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"
        session["_last_improv_song_source"] = "Active song"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["studio_page"] = "creative"
        session["improv_intelligence_tab"] = "Phrase / Motif"
        return session

    def test_motif_chart_key_is_custom_pk_not_leftover_bm(self) -> None:
        from source_session_state import resolve_sbi_preview, sbi_active_should_follow_global_custom

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        self.assertTrue(sbi_active_should_follow_global_custom(session))
        key = _authoritative_practice_chart_key(session, "Bm")
        self.assertEqual(key, "Cm")
        sections = _authoritative_concert_sections(session, {})
        self.assertEqual(sections.get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Trial Song")
        self.assertEqual(preview["display_key"], "Cm")
        self.assertEqual(preview["sections"].get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)
        stale = session.get("catalog_session") or {}
        self.assertEqual((stale.get("selected_song") or {}).get("title"), "Shape of You")
        self.assertEqual(stale.get("display_key"), "Bm")

    def test_backing_does_not_adopt_leftover_display_key_bm(self) -> None:
        from backing_context import BACKING_CONTEXT_KEY, _live_backing_concert_keys, set_backing_context

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        ctx = build_custom_progression_context(session)
        set_backing_context(session, ctx, trace_caller="test_r4_live_stamps")
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        _practice, display, concert = _live_backing_concert_keys(session)
        self.assertEqual(concert, "Cm")
        self.assertEqual(display, "Cm")
        self.assertEqual(_practice, "Cm")
        self.assertEqual(ctx.song_title, "Trial Song")
        rebuilt = build_custom_progression_context(session)
        self.assertEqual(rebuilt.concert_key, "Cm")
        self.assertEqual(rebuilt.progression, ["Cm", "Cm", "Bb", "Bb"])
        self.assertEqual(session.get(BACKING_CONTEXT_KEY, {}).get("source"), "custom_progression")
        _assert_canonical_intact(self, session)

    def test_user_catalog_flag_leftover_does_not_supply_shape_chords(self) -> None:
        """Stale USER_CATALOG without an authoritative catalog epoch must not
        feed Shape chords into Custom Creative. Explicit catalog selection
        (epoch) is the real leave boundary — covered separately.
        """
        from songs.music_source import USER_CATALOG_SOURCE_CHOICE_KEY
        from workflow_musical_authority import custom_owns_active_song_material

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        # Bare leftover flag (no catalog epoch) — Custom activation remains GA.
        session[USER_CATALOG_SOURCE_CHOICE_KEY] = True
        session.pop("_explicit_catalog_selection_epoch", None)
        self.assertTrue(custom_owns_active_song_material(session))
        key = _authoritative_practice_chart_key(session, "Bm")
        sections = _authoritative_concert_sections(session, {"Verse": ["Bm", "A"]})
        self.assertEqual(key, "Cm")
        self.assertEqual(sections.get("Verse"), ["Cm", "Cm", "Bb", "Bb"])
        _assert_canonical_intact(self, session)

    def test_creative_remount_bm_does_not_overwrite_custom_sticky_cm(self) -> None:
        """Live R4 seq295: note_display_key_change(Bm) wrote Shape onto custom::."""
        from songs.key_state import LAST_DISPLAY_KEY, note_display_key_change
        from songs.practice_key_state import get_practice_concert_key

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        pick = str(session.get("active_catalog_pick_key") or "")
        self.assertEqual(get_practice_concert_key(session, pick), "Cm")
        session[LAST_DISPLAY_KEY] = "Cm"
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["studio_page"] = "creative"
        st = SimpleNamespace(session_state=session)
        changed = note_display_key_change(st, "Bm")
        self.assertFalse(changed)
        self.assertEqual(get_practice_concert_key(session, pick), "Cm")
        self.assertEqual(session.get("display_key"), "Cm")
        self.assertEqual(_authoritative_practice_chart_key(session, "Bm"), "Cm")
        _assert_canonical_intact(self, session)

    def test_catalog_reconcile_does_not_write_shape_bm_onto_custom_sticky(self) -> None:
        """Live R4: missions_tab_song_blob_reconcile wrote Bm onto custom:: sticky.

        Sidebar identity prime remounts display_key=Bm (Shape residue) while
        Custom remains GA with sticky Cm — reconcile must not heal that Bm onto
        the custom:: pick.
        """
        from music_workflow_song_practice import (
            ensure_missions_parent_practice_key_hydrated,
            reconcile_catalog_practice_key_owner,
        )

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        pick = str(session.get("active_catalog_pick_key") or "")
        self.assertTrue(pick.startswith("custom::"), pick)
        self.assertEqual(get_practice_concert_key(session, pick), "Cm")
        # Simulate Shape sidebar remount / leftover selected_song while Custom GA.
        session["display_key"] = "Bm"
        session["concert_key"] = "Bm"
        session["song"] = "Shape of You"
        session["selected_song"] = {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": "Pop\x1fShape of You",
        }
        session["studio_page"] = "picker"
        session["improv_intelligence_tab"] = "Harmony Map"
        chosen = reconcile_catalog_practice_key_owner(
            session, source="missions_tab_song_blob_reconcile"
        )
        self.assertEqual(chosen, "Cm")
        self.assertEqual(get_practice_concert_key(session, pick), "Cm")
        token = ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(token, "Cm")
        self.assertEqual(get_practice_concert_key(session, pick), "Cm")
        self.assertEqual(_authoritative_practice_chart_key(session, "Bm"), "Cm")
        _assert_canonical_intact(self, session)

    def test_explicit_leave_custom_still_wins(self) -> None:
        from source_session_state import (
            resolve_sbi_preview,
            sbi_active_should_follow_global_custom,
            stamp_sbi_active_leave_intent,
        )

        session = self._live_stamps(_trial_song_session_with_stale_catalog())
        stamp_sbi_active_leave_intent(session)
        self.assertFalse(sbi_active_should_follow_global_custom(session))
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview["title"], "Shape of You")
        self.assertEqual(preview["display_key"], "Bm")
        _assert_canonical_intact(self, session)


if __name__ == "__main__":
    unittest.main()
