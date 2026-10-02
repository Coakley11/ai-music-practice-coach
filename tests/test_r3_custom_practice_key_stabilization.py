"""R3 — Custom Practice Key workflow stabilization acceptance matrix (C1-C8).

Pure session-state-dict tests calling real production functions directly
(no Streamlit/browser), matching the established R1/R2 test convention
(test_r1_true_source_backing_authority.py, test_r2_mission_owner_key_backing_stability.py).

Primary acceptance journey: Custom song, Original Key D, canonical chords
D - A - Bm - G. Practice Key D -> E -> Eb -> D must project correctly with
zero cumulative drift and without ever rewriting the canonical Original Key
or stored chords.
"""

from __future__ import annotations

import unittest

from backing_context import build_custom_progression_context
from custom_progression_lab import (
    CPL_ACTIVE_KEY,
    apply_cpl_session_progression,
    build_style_preset_entries,
    cpl_active_from_session,
    cpl_draft_written_key,
    cpl_workspace_practice_key,
    display_sections_for_key,
    ensure_original_structure,
    practice_entries_to_original_key,
    start_new_progression,
    sync_custom_workspace_practice_key,
    sync_cpl_draft_widgets_to_active,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CUSTOM,
    custom_pick_key_for,
)
from songs.practice_key_state import get_practice_concert_key


def _chord_symbols(entries: list[dict]) -> list[str]:
    return [str(e.get("chord") or "").strip() for e in entries]


def _make_custom_dagb(session: dict) -> dict:
    """Build a Custom song: Original D, canonical chords D - A - Bm - G."""
    apply_cpl_session_progression(session, start_new_progression(), reset_display_key=True)
    session["cpl_original_key"] = "D"
    active = sync_cpl_draft_widgets_to_active(session, session["cpl_active_progression"])
    practice_entries = build_style_preset_entries("Pop", "I–V–vi–IV", "D")
    active["original_sections"]["Verse"] = practice_entries_to_original_key(
        practice_entries, "D", "D"
    )
    session["cpl_active_progression"] = active
    session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
    return active


class TestC1toC3PrimaryAcceptanceJourney(unittest.TestCase):
    """D(original) -> Practice E -> Practice Eb -> Practice D, zero drift."""

    def test_original_d_initial_state(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        self.assertEqual(cpl_draft_written_key(active), "D")
        self.assertEqual(cpl_workspace_practice_key(session, active), "D")
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            ["D", "A", "Bm", "G"],
        )

    def test_c1_practice_key_e(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        self.assertEqual(cpl_draft_written_key(active), "D", "Original Key must stay D")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
            "canonical chords must be untouched by a Practice Key change",
        )
        projected = display_sections_for_key(active, "E")["Verse"]
        self.assertEqual(_chord_symbols(projected), ["E", "B", "C#m", "A"])

    def test_c2_practice_key_eb_after_e(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        sync_custom_workspace_practice_key(session, practice_key="Eb", active=active)
        self.assertEqual(cpl_draft_written_key(active), "D")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )
        projected = display_sections_for_key(active, "Eb")["Verse"]
        self.assertEqual(_chord_symbols(projected), ["Eb", "Bb", "Cm", "Ab"])

    def test_c3_restore_practice_key_d_no_cumulative_drift(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        sync_custom_workspace_practice_key(session, practice_key="Eb", active=active)
        sync_custom_workspace_practice_key(session, practice_key="D", active=active)
        self.assertEqual(cpl_draft_written_key(active), "D")
        projected = display_sections_for_key(active, "D")["Verse"]
        self.assertEqual(
            _chord_symbols(projected),
            ["D", "A", "Bm", "G"],
            "round trip D->E->Eb->D must return EXACTLY to canonical chords",
        )
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
            "canonical storage must never accumulate transposition drift",
        )

    def test_c3b_every_projection_derives_from_canonical_not_prior_display(self) -> None:
        """Repeated same-key re-projection must be idempotent (no drift)."""
        session: dict = {}
        active = _make_custom_dagb(session)
        for key in ("E", "Eb", "E", "D", "Eb", "D"):
            sync_custom_workspace_practice_key(session, practice_key=key, active=active)
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active, "D")["Verse"]),
            ["D", "A", "Bm", "G"],
        )


class TestC4RefreshRemount(unittest.TestCase):
    def test_non_original_practice_key_survives_remount(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        pick = custom_pick_key_for(active)
        self.assertEqual(get_practice_concert_key(session, pick), "E")

        # Simulate remount: rebuild "active" purely from the persisted session dict,
        # the way a fresh script run would via cpl_active_from_session.
        remounted_active = ensure_original_structure(session[CPL_ACTIVE_KEY])
        self.assertEqual(cpl_draft_written_key(remounted_active), "D")
        self.assertEqual(get_practice_concert_key(session, pick), "E")
        projected = display_sections_for_key(remounted_active, "E")["Verse"]
        self.assertEqual(_chord_symbols(projected), ["E", "B", "C#m", "A"])
        self.assertEqual(
            _chord_symbols(remounted_active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )


class TestC5CustomToBackingAndReturn(unittest.TestCase):
    def test_backing_uses_same_practice_key_projection(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)

        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.concert_key, "E")
        self.assertEqual(ctx.progression, ["E", "B", "C#m", "A"])

        # Original/canonical must remain untouched by entering Backing.
        self.assertEqual(cpl_draft_written_key(session[CPL_ACTIVE_KEY]), "D")
        self.assertEqual(
            _chord_symbols(session[CPL_ACTIVE_KEY]["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )

        # Return from Backing: Practice Key E must still be in effect.
        active_after = cpl_active_from_session(session)
        self.assertEqual(cpl_workspace_practice_key(session, active_after), "E")
        self.assertEqual(
            _chord_symbols(display_sections_for_key(active_after, "E")["Verse"]),
            ["E", "B", "C#m", "A"],
        )


class TestC6NewCustomSongInC(unittest.TestCase):
    def test_new_song_original_and_practice_both_c(self) -> None:
        session: dict = {
            "display_key": "E",
            "concert_key": "E",
            "practice_key_by_source": {"custom::old": "E"},
        }
        apply_cpl_session_progression(session, start_new_progression(), reset_display_key=True)
        active = session[CPL_ACTIVE_KEY]
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        self.assertEqual(cpl_draft_written_key(active), "C")
        self.assertEqual(cpl_workspace_practice_key(session, active), "C")

    def test_refresh_remains_c(self) -> None:
        session: dict = {}
        apply_cpl_session_progression(session, start_new_progression(), reset_display_key=True)
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        remounted = ensure_original_structure(session[CPL_ACTIVE_KEY])
        self.assertEqual(cpl_draft_written_key(remounted), "C")
        self.assertEqual(cpl_workspace_practice_key(session, remounted), "C")

    def test_backing_entry_does_not_mutate_original_or_practice(self) -> None:
        session: dict = {}
        apply_cpl_session_progression(session, start_new_progression(), reset_display_key=True)
        session[ACTIVE_MUSIC_SOURCE_KEY] = SOURCE_CUSTOM
        ctx = build_custom_progression_context(session)
        self.assertEqual(ctx.concert_key, "C")
        active_after = cpl_active_from_session(session)
        self.assertEqual(cpl_draft_written_key(active_after), "C")
        self.assertEqual(cpl_workspace_practice_key(session, active_after), "C")


class TestC7BuilderPresetConsistency(unittest.TestCase):
    def test_preset_entries_follow_current_practice_key(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        practice_now = cpl_workspace_practice_key(session, active)
        self.assertEqual(practice_now, "E")
        preset = _chord_symbols(build_style_preset_entries("Pop", "I–V–vi–IV", practice_now))
        self.assertEqual(preset, ["E", "B", "C#m", "A"])

    def test_preset_does_not_permanently_transpose_canonical(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        build_style_preset_entries("Pop", "I–V–vi–IV", "E")
        build_style_preset_entries("Pop", "I–V–vi–IV", "Eb")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
            "calling a builder/preset in a Practice Key must not mutate canonical Original data",
        )


class TestC8SourceIsolation(unittest.TestCase):
    def test_stale_catalog_sticky_does_not_steal_custom_practice_key(self) -> None:
        session: dict = {
            "practice_key_by_source": {"Jewish|Hevenu": "Bm"},
            "active_catalog_pick_key": "Jewish|Hevenu",
        }
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        pick = custom_pick_key_for(active)
        self.assertEqual(get_practice_concert_key(session, pick), "E")
        self.assertEqual(get_practice_concert_key(session, "Jewish|Hevenu"), "Bm")
        self.assertEqual(cpl_workspace_practice_key(session, active), "E")

    def test_stale_mission_jam_context_does_not_steal_custom_practice_key_on_hydrate(self) -> None:
        session: dict = {
            "improv_mission_concert_key": "A#m",
            "_mission_backing_handoff_practice_key": "A#m",
            "improv_intelligence_tab": "Missions",
        }
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        remounted = ensure_original_structure(session[CPL_ACTIVE_KEY])
        self.assertEqual(cpl_workspace_practice_key(session, remounted), "E")
        self.assertEqual(cpl_draft_written_key(remounted), "D")

    def test_stale_jam_key_context_does_not_steal_custom_practice_key(self) -> None:
        session: dict = {
            "improv_jam_key": "F#",
            "improv_style_key": "F#",
        }
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        self.assertEqual(cpl_workspace_practice_key(session, active), "E")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )


if __name__ == "__main__":
    unittest.main()
