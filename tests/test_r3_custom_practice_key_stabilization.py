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

from backing_context import build_custom_progression_context, restore_custom_song_backing
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
    prepare_cpl_backing_handoff,
    start_new_progression,
    sync_custom_workspace_practice_key,
    sync_cpl_draft_widgets_to_active,
)
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    SOURCE_CATALOG,
    SOURCE_CUSTOM,
    commit_custom_active_song,
    custom_pick_key_for,
)
from songs.practice_key_state import get_practice_concert_key, mark_practice_key_user_override
from backing_source_navigation import (
    BACKING_ENTRY_CLASS_KEY,
    BACKING_ENTRY_SPECIALIZED_HANDOFF,
    BACKING_INTENT_FROM_CREATIVE,
    consume_backing_open_intent,
)


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


class TestOpenBackingSealsSpecializedHandoff(unittest.TestCase):
    """Regression: Open in Backing Studio from CPL must stamp a specialized
    handoff (entry_class + intent) so hydrate_backing_source_for_page routes
    to the custom_progression context instead of falling through to the
    entry_jam default, which raised CreativeBackingHandoffBlocked."""

    def test_prepare_cpl_backing_handoff_seals_specialized_entry(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        prepare_cpl_backing_handoff(session, active, section=None)
        self.assertEqual(session.get(BACKING_ENTRY_CLASS_KEY), BACKING_ENTRY_SPECIALIZED_HANDOFF)
        self.assertEqual(session.get("_backing_explicit_handoff_source"), "custom_progression")

    def test_prepare_cpl_backing_handoff_intent_is_from_creative(self) -> None:
        session: dict = {}
        active = _make_custom_dagb(session)
        prepare_cpl_backing_handoff(session, active, section=None)
        self.assertEqual(consume_backing_open_intent(session), BACKING_INTENT_FROM_CREATIVE)


class TestSetActiveSongPreservesExplicitPracticeKey(unittest.TestCase):
    """Regression: clicking Set as Active Song on a Custom draft whose Practice
    Key was deliberately changed before activation (explicit sidebar edit,
    durable override marker set) must not silently reset Practice Key back to
    Original — only a genuinely different prior source's stale residue should
    be discarded, not this pick's own deliberate edit."""

    def test_explicit_practice_key_survives_set_active_song(self) -> None:
        from types import SimpleNamespace

        session: dict = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG}
        active = _make_custom_dagb(session)
        pick = custom_pick_key_for(active)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        mark_practice_key_user_override(session, pick)
        st = SimpleNamespace(session_state=session)

        commit_custom_active_song(st, active, invalidate_backing=lambda *a, **k: None)

        self.assertEqual(get_practice_concert_key(session, pick), "E")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )

    def test_without_override_marker_fresh_activation_still_resets(self) -> None:
        """Sanity check: the protection is specific to a real override marker —
        genuine stale residue in the sticky store (never a deliberate edit via
        the real Practice Key change path, so no override marker was ever set)
        still resets to Original on fresh activation, preserving the original
        anti-leak contract this code existed to enforce."""
        from types import SimpleNamespace

        session: dict = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG}
        active = _make_custom_dagb(session)
        pick = custom_pick_key_for(active)
        # Raw stale residue written directly to the sticky store — bypasses the
        # real on_change path, so it never marks the durable override (matches
        # sync_custom_workspace_practice_key's own internal behavior: a real
        # deliberate Practice Key edit always marks the override, so this
        # distinguishes stale residue from a genuine prior edit).
        session.setdefault("practice_key_by_source", {})[pick] = "E"
        st = SimpleNamespace(session_state=session)

        commit_custom_active_song(st, active, invalidate_backing=lambda *a, **k: None)

        self.assertEqual(get_practice_concert_key(session, pick), "D")


class TestOpenBackingStudioPreservesExplicitPracticeKey(unittest.TestCase):
    """R5 regression: restore_custom_song_backing (the Backing-page hydrate path
    hit via "Open in Backing Studio" -> hydrate_backing_source_for_page ->
    activate_custom_ownership) forced reset_practice_to_original=True
    unconditionally, which skips commit_custom_active_song's own explicit-
    override guard entirely and reseals Original Key over a Practice Key the
    user had just deliberately set (e.g. Trial Song Original Em, Practice Cm
    -> Open in Backing Studio showed Em instead of Cm)."""

    def test_explicit_practice_key_survives_open_backing_studio(self) -> None:
        from types import SimpleNamespace

        session: dict = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM}
        active = _make_custom_dagb(session)
        pick = custom_pick_key_for(active)
        sync_custom_workspace_practice_key(session, practice_key="E", active=active)
        mark_practice_key_user_override(session, pick)
        st = SimpleNamespace(session_state=session)

        restore_custom_song_backing(session, st_like=st)

        self.assertEqual(get_practice_concert_key(session, pick), "E")
        self.assertEqual(
            _chord_symbols(active["original_sections"]["Verse"]),
            ["D", "A", "Bm", "G"],
        )

    def test_without_override_marker_open_backing_studio_still_resets(self) -> None:
        """Sanity check: a custom pick with no durable override marker (never
        a deliberate Practice Key edit through the real on_change path) still
        resets to Original on this restore path, preserving the original
        anti-leak contract."""
        from types import SimpleNamespace

        session: dict = {ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CUSTOM}
        active = _make_custom_dagb(session)
        pick = custom_pick_key_for(active)
        session.setdefault("practice_key_by_source", {})[pick] = "E"
        st = SimpleNamespace(session_state=session)

        restore_custom_song_backing(session, st_like=st)

        self.assertEqual(get_practice_concert_key(session, pick), "D")


if __name__ == "__main__":
    unittest.main()
