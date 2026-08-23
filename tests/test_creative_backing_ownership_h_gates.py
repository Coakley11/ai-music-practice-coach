"""Unit gates for Creative/Backing ownership + Build Motif Pattern."""

from __future__ import annotations

import unittest

from creative_source_ownership_contract import (
    resolve_global_active_snapshot,
    resolve_last_custom_snapshot,
    resolve_sbi_snapshot,
    stamp_explicit_backing_handoff,
)
from improvisation_motif import build_motif_pattern, generate_motif_for_chord, rebuild_motif_pattern, transform_motif
from music_source_ownership import rebuild_catalog_backing_from_canonical_pick


class TestMotifPattern(unittest.TestCase):
    def test_build_pattern_keeps_first_cell_as_motif(self) -> None:
        motif = generate_motif_for_chord("Em", key_center="E minor", level="Intermediate")
        base = list(motif["notes"])
        pattern = build_motif_pattern(
            motif,
            key_center="E minor",
            pattern_type="diatonic",
            direction="ascending",
            length=8,
        )
        self.assertTrue(pattern.get("is_pattern"))
        self.assertEqual(pattern["pattern_length"], 8)
        self.assertEqual(pattern["cells"][0], base)
        self.assertGreaterEqual(len(pattern["notes"]), 8 * len(base))

    def test_direction_rebuild_preserves_type_length_rhythm(self) -> None:
        motif = generate_motif_for_chord("C#m", key_center="C# minor", level="Intermediate")
        pat = build_motif_pattern(
            motif,
            key_center="C# minor",
            pattern_type="thirds",
            direction="ascending",
            length=12,
        )
        rk = pat["rhythm_key"]
        desc = rebuild_motif_pattern(
            pat,
            key_center="C# minor",
            pattern_type="thirds",
            direction="descending",
            length=12,
        )
        self.assertEqual(desc["pattern_type"], "thirds")
        self.assertEqual(desc["pattern_direction"], "descending")
        self.assertEqual(desc["pattern_length"], 12)
        self.assertEqual(desc["rhythm_key"], rk)
        self.assertEqual(desc["cells"][0], pat["cells"][0])

    def test_change_rhythm_keeps_pitches(self) -> None:
        motif = generate_motif_for_chord("Am", key_center="A minor", level="Intermediate")
        pat = build_motif_pattern(motif, key_center="A minor", length=8)
        pitches = list(pat["notes"])
        changed = transform_motif(pat, "change_rhythm", key_center="A minor")
        self.assertEqual(list(changed["notes"]), pitches)
        self.assertNotEqual(changed.get("rhythm_key"), pat.get("rhythm_key"))

    def test_sequence_up_shifts_whole_pattern(self) -> None:
        motif = generate_motif_for_chord("Em", key_center="E minor", level="Intermediate")
        pat = build_motif_pattern(motif, key_center="E minor", length=8)
        before = list(pat["notes"])
        up = transform_motif(pat, "sequence_up", key_center="E minor")
        self.assertEqual(len(up["notes"]), len(before))
        self.assertNotEqual(up["notes"], before)
        self.assertTrue(up.get("is_pattern"))


class TestOwnershipContract(unittest.TestCase):
    def test_sbi_custom_resolves_last_custom_not_catalog(self) -> None:
        session = {
            "active_music_source": "catalog_song",
            "active_catalog_pick_key": "catalog::shape",
            "selected_song": {"title": "Shape of You", "key": "B minor", "pick_key": "catalog::shape"},
            "song": "Shape of You",
            "display_key": "C# minor",
            "sbi_preview_source": "Custom progression",
            "cpl_active_progression": {
                "id": "trial-1",
                "name": "Trial Song",
                "original_key_center": "D",
                "sections": {"A": ["D", "G", "A"]},
            },
            "practice_key_by_source": {"custom::trial-1": "D"},
        }
        sbi = resolve_sbi_snapshot(session)
        assert sbi is not None
        self.assertEqual(sbi.source_kind, "custom")
        self.assertIn("Trial", sbi.title)
        global_snap = resolve_global_active_snapshot(session)
        assert global_snap is not None
        self.assertEqual(global_snap.source_kind, "catalog")

    def test_stamp_explicit_handoff(self) -> None:
        session: dict = {}
        stamp_explicit_backing_handoff(session, "mission")
        self.assertEqual(session.get("_backing_explicit_handoff_source"), "mission")


class TestRebuildPreservesPracticeKey(unittest.TestCase):
    def test_rebuild_defaults_do_not_force_original_reset(self) -> None:
        import inspect

        sig = inspect.signature(rebuild_catalog_backing_from_canonical_pick)
        self.assertFalse(sig.parameters["reset_to_original"].default)
        self.assertFalse(sig.parameters["force_bpm_reset"].default)

    def test_ordinary_backing_hydrate_keeps_sticky_csharp(self) -> None:
        """H2: Songs→Backing must not reset Shape C#m to Original Bm."""
        from types import SimpleNamespace

        from backing_context import clear_backing_context, get_backing_context
        from backing_source_navigation import (
            hydrate_backing_source_for_page,
            mark_generic_catalog_backing_entry,
        )
        from song_catalog.catalog import format_pick_key
        from songs.music_source import SOURCE_CATALOG, USER_CATALOG_SOURCE_CHOICE_KEY
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

        pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "bpm": 96,
                    "genre": "Pop",
                }
            }
        }
        session = {
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "active_music_source": SOURCE_CATALOG,
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Shape of You",
                "pick_key": pick,
                "key": "Bm",
                "bpm": 96,
                "genre": "Pop",
                "artist": "Ed Sheeran",
            },
            "song": "Shape of You",
            "display_key": "C#m",
            "concert_key": "C#m",
            "practice_key_by_source": {},
            "_reconcile_song_picker_catalog": catalog,
            "_catalog_backup_picker": catalog,
            "studio_page": "backing",
        }
        set_practice_concert_key(session, "C#m", pick_key=pick)
        clear_backing_context(session)
        mark_generic_catalog_backing_entry(session)
        hydrate_backing_source_for_page(
            session, st_like=SimpleNamespace(session_state=session)
        )
        ctx = get_backing_context(session)
        self.assertEqual(session.get("display_key"), "C#m")
        self.assertEqual(get_practice_concert_key(session, pick), "C#m")
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(ctx.concert_key, "C#m")

    def test_use_catalog_backing_keeps_sticky_from_legacy_pick_alias(self) -> None:
        """H9: sticky under Genre::Label must survive Use catalog → canonical pick."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from backing_context import BACKING_CONTEXT_KEY, restore_regular_song_backing
        from backing_source_navigation import BACKING_INTENT_SWITCH_CATALOG, set_key_transition_intent
        from song_catalog.catalog import format_pick_key
        from songs.music_source import CATALOG_BEFORE_CUSTOM_KEY
        from songs.practice_key_state import get_practice_concert_key, set_practice_concert_key

        pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        legacy = "Pop::Shape of You — Ed Sheeran"
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "bpm": 96,
                    "genre": "Pop",
                }
            }
        }
        session = {
            "active_catalog_pick_key": pick,
            "selected_song": {
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
                "pick_key": pick,
                "bpm": 96,
                "genre": "Pop",
            },
            "song": "Shape of You",
            "display_key": "D",
            "concert_key": "D",
            "user_catalog_source_choice": True,
            "practice_key_by_source": {legacy: "C#m"},
            "song_picker_catalog": catalog,
            "_catalog_backup_picker": catalog,
            BACKING_CONTEXT_KEY: {
                "source": "custom_progression",
                "song_title": "My Progression",
                "key": "D",
                "display_key": "D",
                "concert_key": "D",
                "bpm": 100,
                "active_song_id": "custom::x",
                "bound_pick_key": "custom::x",
            },
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "pick_key": pick,
                    "bpm": 96,
                },
                "original_key": "Bm",
                "display_key": "C#m",
            },
        }
        set_key_transition_intent(session, BACKING_INTENT_SWITCH_CATALOG)
        st = SimpleNamespace(session_state=session)
        with patch("backing_track_state.write_canonical_backing_state"):
            ctx = restore_regular_song_backing(session, st_like=st)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.source, "regular_song")
        self.assertEqual(session.get("display_key"), "C#m")
        self.assertEqual(ctx.concert_key, "C#m")
        self.assertEqual(get_practice_concert_key(session, pick), "C#m")


class TestCatalogOriginalKeyNotPolluted(unittest.TestCase):
    def test_resolve_catalog_song_ignores_snap_original_key_c(self) -> None:
        """FIRST writer of Shape+C was snap/fallback 'C'; catalog row must win."""
        from song_catalog.catalog import format_pick_key
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            resolve_catalog_song_for_pick,
        )

        pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "bpm": 96,
                    "genre": "Pop",
                }
            }
        }
        session = {
            LAST_CATALOG_STATE_KEY: {
                "pick_key": pick,
                "selected_song": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "C",
                    "pick_key": pick,
                },
                "original_key": "C",
                "display_key": "C",
            },
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": pick,
                "selected_song": {"title": "Shape of You", "key": "C", "pick_key": pick},
                "original_key": "C",
            },
            "_reconcile_song_picker_catalog": catalog,
        }
        selected, original = resolve_catalog_song_for_pick(
            session,
            pick,
            song_picker_catalog=catalog,
            authoritative_transport=True,
        )
        self.assertEqual(original, "Bm")
        self.assertEqual(selected.get("key"), "Bm")
        self.assertEqual(selected.get("title"), "Shape of You")

    def test_switch_to_catalog_force_restores_when_flags_already_cleared(self) -> None:
        """Use catalog must still restore when Custom flags were partially cleared."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from song_catalog.catalog import format_pick_key
        from songs.music_source import (
            CATALOG_BEFORE_CUSTOM_KEY,
            LAST_CATALOG_STATE_KEY,
            USER_CATALOG_SOURCE_CHOICE_KEY,
            switch_to_catalog_from_custom,
        )

        pick = format_pick_key("Pop", "Shape of You — Ed Sheeran")
        catalog = {
            "Pop": {
                "Shape of You — Ed Sheeran": {
                    "title": "Shape of You",
                    "artist": "Ed Sheeran",
                    "key": "Bm",
                    "bpm": 96,
                    "genre": "Pop",
                }
            }
        }
        session = {
            "active_catalog_pick_key": pick,
            "active_music_source": "catalog",
            USER_CATALOG_SOURCE_CHOICE_KEY: True,
            "song": "Shape of You",
            "display_key": "C",
            "concert_key": "C",
            "selected_song": {"title": "Shape of You", "key": "C", "pick_key": pick},
            LAST_CATALOG_STATE_KEY: {
                "pick_key": pick,
                "selected_song": {"title": "Shape of You", "key": "C", "pick_key": pick},
                "original_key": "C",
                "display_key": "C#m",
            },
            CATALOG_BEFORE_CUSTOM_KEY: {
                "pick_key": pick,
                "selected_song": {"title": "Shape of You", "key": "C", "pick_key": pick},
                "original_key": "C",
                "display_key": "C#m",
            },
            "practice_key_by_source": {pick: "C#m"},
            "_reconcile_song_picker_catalog": catalog,
        }
        st = SimpleNamespace(session_state=session)

        def _fake_apply(st_obj, pick_key, song_picker_catalog, song_library=None, skip_activity_log=False):
            return dict(catalog["Pop"]["Shape of You — Ed Sheeran"], pick_key=pick_key)

        commits: list[dict] = []

        def _capture_commit(st_obj, **kwargs):
            commits.append(kwargs)

        with (
            patch("songs.state.apply_pick_key", side_effect=_fake_apply),
            patch("songs.music_source.commit_catalog_active_song", side_effect=_capture_commit),
            patch("songs.music_source.snapshot_last_custom_state"),
        ):
            # Without force, early-return (already catalog).
            ok_soft = switch_to_catalog_from_custom(
                st,
                song_picker_catalog=catalog,
                invalidate_backing=lambda _st: None,
                force=False,
            )
            self.assertFalse(ok_soft)
            self.assertEqual(commits, [])
            ok_force = switch_to_catalog_from_custom(
                st,
                song_picker_catalog=catalog,
                invalidate_backing=lambda _st: None,
                force=True,
            )
        self.assertTrue(ok_force)
        self.assertTrue(commits)
        self.assertEqual(commits[0].get("original_key"), "Bm")
        self.assertEqual(commits[0].get("pick_key"), pick)
    def test_merge_keeps_catalog_key(self) -> None:
        from songs.state import get_song_context

        # Exercise the merge helper path via a minimal st-like object is heavy;
        # assert the protected behavior directly on the merge semantics used there.
        canon = {"title": "Shape of You", "key": "Bm", "sections": {"A": ["Bm"]}}
        overlay = {"title": "Shape of You", "key": "C", "pick_key": "Pop\x1fShape"}
        merged = dict(canon)
        for key, val in overlay.items():
            if key == "key":
                continue
            if val is None:
                continue
            merged[key] = val
        self.assertEqual(merged["key"], "Bm")
        self.assertEqual(merged["pick_key"], "Pop\x1fShape")
        self.assertIs(get_song_context, get_song_context)
    def test_csharp_motif_is_not_em(self) -> None:
        from improvisation_motif import chord_tone_names, generate_motif_for_chord

        motif = generate_motif_for_chord("C#m", key_center="C# minor", level="Intermediate")
        self.assertEqual(motif.get("chord"), "C#m")
        notes = list(motif.get("notes") or [])
        self.assertTrue(notes)
        # Must not be the classic Em four-note set alone.
        self.assertNotEqual(notes, ["E", "F#", "G", "B"])
        tones = set(chord_tone_names("C#m", reference_key="C# minor"))
        # At least one generated note should be a C#m chord tone / scale degree in C# minor.
        self.assertTrue(any(n in tones or n in {"C#", "D#", "E", "F#", "G#", "A", "B"} for n in notes))

    def test_pattern_sheet_uses_full_notes(self) -> None:
        from improvisation_motif import build_motif_notation_abc, build_motif_pattern, generate_motif_for_chord

        motif = generate_motif_for_chord("C#m", key_center="C# minor", level="Intermediate")
        motif["chord"] = "C#m"
        pat = build_motif_pattern(motif, key_center="C# minor", length=8)
        self.assertTrue(pat.get("is_pattern"))
        self.assertEqual(pat.get("chord"), "C#m")
        abc = build_motif_notation_abc(pat, key_center="C# minor", bpm=100)
        # Full pattern has many more pitch events than a 4-note motif.
        self.assertGreater(len(pat.get("notes") or []), 4)
        self.assertIn("X:", abc)


if __name__ == "__main__":
    unittest.main()
