"""Human-QA Creative/SBI/Missions/Backing/Motif coherence regressions.

Covers the 12 demonstrated failures from Creative Stabilization visual QA.
Does not weaken unrelated integrity checks.
"""

from __future__ import annotations

import copy
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from backing_context import (
    BACKING_CONTEXT_KEY,
    _entry_jam_context_from_owner_snapshot,
    build_mission_context,
    open_backing_from_creative,
)
from backing_source_navigation import hydrate_backing_source_for_page
from creative_key_sync import _catalog_song_workflow_owns_practice_key
from generated_workflow_artifact import GeneratedWorkflowArtifactSnapshot
from harmonic_spelling import apply_motif_chord_spelling, harmonic_reference_for_chord
from improvisation_motif import (
    _abc_key_header,
    build_motif_abc,
    build_motif_pattern,
    generate_motif_for_chord,
    transform_motif,
)
from mission_backing_alignment import build_mission_backing_alignment_payload
from mission_return_destination import (
    MISSION_CANONICAL_RETURN_DESTINATION_KEY,
    apply_sealed_mission_return_destination,
    build_mission_return_destination,
    seal_mission_return_destination,
)
from music_workflow_pending_creative_return import (
    PENDING_CREATIVE_RETURN_KEY,
    consume_pending_creative_return_handoff,
    handle_return_to_creative_click,
    queue_pending_creative_return_from_backing,
)
from music_workflow_pending_mission_return import (
    consume_pending_mission_return_handoff,
    queue_pending_mission_return_from_backing,
)
from songs.music_source import LAST_CUSTOM_STATE_KEY
from songs.practice_key_state import (
    get_practice_concert_key,
    resolve_settings_pick_for_write,
    set_practice_concert_key,
)
from source_session_state import custom_sbi_owns_sidebar_practice_key


SHAPE = "Pop\x1fShape of You — Ed Sheeran"
TRIAL = "custom::trial-qa-1"


def _shape_catalog_session(**extra: object) -> dict:
    session: dict = {
        "studio_page": "creative",
        "improv_intelligence_tab": "Song-Based Improvisation",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "active_catalog_pick_key": SHAPE,
        "song": "Shape of You",
        "display_key": "Am",
        "concert_key": "Am",
        "selected_song": {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
            "pick_key": SHAPE,
        },
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": TRIAL,
            "custom_home_key": "D",
            "active": {
                "id": "trial-qa-1",
                "name": "Trial Song",
                "original_key_center": "D",
            },
        },
        "practice_key_by_source": {SHAPE: "Am", TRIAL: "D"},
    }
    session.update(extra)
    return session


def _bossa_snapshot(*, tonic: str = "C", mode: str = "major") -> GeneratedWorkflowArtifactSnapshot:
    return GeneratedWorkflowArtifactSnapshot(
        workflow_owner="style_jam",
        workflow_session_id=str(uuid.uuid4()),
        artifact_id=str(uuid.uuid4()),
        artifact_revision=1,
        generation_request_token="qa-bossa",
        generation_sequence=1,
        control_fingerprint="qa-bossa-fp",
        practice_tonic=tonic,
        practice_mode=mode,
        style="Bossa Nova",
        mood="Mellow",
        groove="",
        intensity="Medium",
        bpm=110,
        meter="4/4",
        level="Intermediate",
        section_map={"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
        selected_scope="Full song",
        selected_section_ids=["A (Bossa Nova)"],
        progression=["Dm7", "G7", "Cmaj7"],
        backing_configuration={},
        exact_return_destination="creative",
        entry_mode="Style Jam Mode",
        bound_pick_key="",
    )


class Test1CustomLabPresentation(unittest.TestCase):
    def test_open_custom_lab_label_keeps_text_and_uses_page_icon(self) -> None:
        from app_ui import STUDIO_PAGE_META
        import improvisation_intelligence_ui as ui_mod
        import inspect

        icon = str(STUDIO_PAGE_META.get("custom", {}).get("icon") or "")
        self.assertTrue(icon)
        src = inspect.getsource(ui_mod)
        self.assertIn("Open Custom Lab", src)
        self.assertIn("STUDIO_PAGE_META", src)
        self.assertIn(icon, src)


class Test2CustomSbiMissionsPracticeKey(unittest.TestCase):
    def test_custom_sbi_preview_does_not_own_missions_sidebar_when_catalog_ga(self) -> None:
        session = _shape_catalog_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            display_key="Eb",
            concert_key="Eb",
            improv_intelligence_tab="Entry & Jam",
        )
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))
        session["improv_intelligence_tab"] = "Missions"
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))
        write = resolve_settings_pick_for_write(session)
        self.assertFalse(str(write).startswith("custom::"), write)

    def test_custom_ga_missions_still_owns_custom_sidebar(self) -> None:
        session = _shape_catalog_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Missions",
            active_catalog_pick_key=TRIAL,
            selected_song={"title": "Trial Song", "key": "D", "pick_key": TRIAL},
            display_key="E",
            concert_key="E",
        )
        from songs.music_source import SOURCE_CUSTOM

        session["active_music_source"] = SOURCE_CUSTOM
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))


class Test3MissionBackingRoundTrip(unittest.TestCase):
    def _mission_session(self, chord: str, *, idx: int = 2) -> dict:
        session = _shape_catalog_session(
            improv_intelligence_tab="Missions",
            improv_active_mission="Outline chord tones",
            improv_mission_pick="Outline chord tones",
            ii_selected_chord=chord,
            II_SELECTED_CHORD=chord,
            ii_selected_section="Chorus",
            ii_selected_chord_index=idx,
            improv_mission_chord_options=["Bm", "F#m", chord, "Em"],
            display_key="Am",
            concert_key="Am",
            instrument="Piano",
        )
        return session

    def _round_trip(self, chord: str) -> dict:
        session = self._mission_session(chord)
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord=chord,
            section_label="Chorus",
            chord_idx=2,
            song_title="Shape of You",
            with_practice_lick=True,
        )
        dest = build_mission_return_destination(
            align,
            handoff_mode="practice_in_jam",
            with_practice_lick=True,
            request_seq=1,
        )
        seal_mission_return_destination(session, dest)
        ctx = build_mission_context(session)
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        self.assertEqual(ctx.source, "mission")
        self.assertIn(chord, " ".join(ctx.progression or []) + " " + str(ctx.progression_label or ""))
        self.assertNotEqual(str(ctx.progression_label or ""), "F")
        if ctx.progression:
            self.assertNotEqual(ctx.progression[0], "F")
        sealed = session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY)
        self.assertIsInstance(sealed, dict)
        self.assertEqual(sealed.get("creative_tab"), "Missions")
        self.assertEqual(sealed.get("chord_symbol"), chord)
        session["studio_page"] = "backing"
        session["improv_intelligence_tab"] = "Song-Based Improvisation"
        queue_pending_mission_return_from_backing(session)
        with mock.patch("music_workflow_activation.activate_workflow_simple") as activate:
            activate.return_value = mock.Mock(ok=True, trace={})
            with mock.patch(
                "mission_backing_alignment.apply_pending_mission_backing_alignment",
                return_value=True,
            ):
                phase = consume_pending_mission_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(session.get("studio_page"), "creative")
        apply_sealed_mission_return_destination(session)
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(session.get("ii_selected_chord"), chord)
        return session

    def test_a_major_mission_backing_round_trip(self) -> None:
        self._round_trip("A")

    def test_non_tonic_fsharp_minor_round_trip(self) -> None:
        self._round_trip("F#m")


class Test4StyleJamBossaMetadata(unittest.TestCase):
    def test_bossa_snapshot_does_not_emit_pop_groove(self) -> None:
        session = {
            "improv_groove": "Pop groove",
            "backing_groove_style": "Pop groove",
            "improv_style": "Pop",
            "active_catalog_pick_key": SHAPE,
        }
        ctx = _entry_jam_context_from_owner_snapshot(session, _bossa_snapshot())
        joined = " ".join(
            [
                str(ctx.style or ""),
                str(ctx.groove or ""),
                str(getattr(ctx, "progression_label", "") or ""),
            ]
        )
        self.assertIn("Bossa", joined)
        self.assertNotIn("Pop", str(ctx.groove or ""))
        self.assertNotIn("Pop groove", joined.lower().replace("bossa", ""))


class Test5And6JamBackingKeyAndHandoff(unittest.TestCase):
    def test_leftover_motif_tab_does_not_own_jam_backing_pk(self) -> None:
        session = _shape_catalog_session(
            studio_page="backing",
            improv_intelligence_tab="Phrase / Motif",
            improv_entry_mode="Style Jam Mode",
        )
        session[BACKING_CONTEXT_KEY] = {
            "source": "entry_jam",
            "style": "Bossa Nova",
            "groove": "Bossa nova",
            "display_key": "C",
            "concert_key": "C",
        }
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))

    def test_entry_jam_handoff_flag_blocks_catalog_pk_steal(self) -> None:
        session = _shape_catalog_session(
            studio_page="creative",
            improv_intelligence_tab="Phrase / Motif",
            improv_entry_mode="Style Jam Mode",
            _backing_explicit_handoff_source="entry_jam",
        )
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))

    def test_open_entry_jam_backing_with_leftover_motif_tab(self) -> None:
        from music_workflow_generated_session import commit_jam_session_generation
        from musical_context_coherence import CreativeBackingHandoffBlocked

        sid = str(uuid.uuid4())
        jam = {
            "id": sid,
            "key": "C",
            "style": "Bossa Nova",
            "ensemble": "Jazz trio",
            "prompt": "**Jazz trio** in **C** · Bossa Nova · ~110 BPM · qa.",
            "sections": {"A (Bossa Nova)": ["Dm7", "G7", "Cmaj7"]},
        }
        session: dict = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "C",
            "improv_jam_mood": "Mellow",
            "improv_generated_sections": copy.deepcopy(jam["sections"]),
            "display_key": "C",
            "concert_key": "C",
            "studio_page": "creative",
            "improv_intelligence_tab": "Phrase / Motif",
            "active_catalog_pick_key": SHAPE,
            "song": "Shape of You",
            "selected_song": {"title": "Shape of You", "key": "Bm", "pick_key": SHAPE},
            "practice_key_by_source": {SHAPE: "Am"},
        }
        commit_jam_session_generation(
            session,
            jam,
            key_center="C",
            style="Bossa Nova",
            new_session=True,
        )
        try:
            ctx = open_backing_from_creative(session, source="entry_jam")
        except CreativeBackingHandoffBlocked as exc:
            self.fail(f"handoff blocked with leftover Motif tab: {exc}")
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "entry_jam")
        self.assertIn("Bossa", f"{ctx.style} {ctx.groove}")
        self.assertNotIn("Pop", str(ctx.groove or ""))

    def test_jam_backing_pk_change_does_not_write_catalog(self) -> None:
        from generated_jam_key_change import mutate_generated_practice_key_from_control
        from music_workflow_generated_session import commit_jam_session_generation
        from music_workflow_state_store import get_active_workflow_pointer, get_workflow_blob

        sid = str(uuid.uuid4())
        jam = {
            "id": sid,
            "key": "C",
            "style": "Bossa Nova",
            "ensemble": "Jazz trio",
            "prompt": "**Jazz trio** in **C** · Bossa Nova",
            "sections": {"A": ["Dm7", "G7", "Cmaj7"]},
        }
        session: dict = {
            "improv_entry_mode": "Style Jam Mode",
            "improv_style": "Bossa Nova",
            "improv_style_key": "C",
            "display_key": "C",
            "concert_key": "C",
            "studio_page": "backing",
            "practice_key_by_source": {SHAPE: "Am", TRIAL: "D"},
        }
        commit_jam_session_generation(
            session, jam, key_center="C", style="Bossa Nova", new_session=True
        )
        session[BACKING_CONTEXT_KEY] = {
            "source": "entry_jam",
            "style": "Bossa Nova",
            "groove": "Bossa nova",
            "display_key": "C",
            "concert_key": "C",
        }
        # Leftover Motif tab after generate must not steal writes or block mutate.
        session["improv_intelligence_tab"] = "Phrase / Motif"
        session["active_catalog_pick_key"] = SHAPE
        session["_backing_explicit_handoff_source"] = "entry_jam"
        write = resolve_settings_pick_for_write(session)
        self.assertFalse(str(write).startswith("Pop"), write)
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))
        self.assertTrue(mutate_generated_practice_key_from_control(session, "D", control="sidebar"))
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Am")
        self.assertEqual(get_practice_concert_key(session, TRIAL), "D")
        ptr = get_active_workflow_pointer(session)
        assert ptr is not None
        blob = get_workflow_blob(session, ptr.workflow_owner, ptr.workflow_session_id)
        assert blob is not None
        self.assertEqual(str(blob.keys.practice_tonic), "D")
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))
        self.assertEqual(str(blob.keys.practice_tonic), "D")


class Test7OneClickReturnToCreative(unittest.TestCase):
    def test_hydrate_consumes_pending_return_without_reclaiming_backing(self) -> None:
        session = _shape_catalog_session(
            studio_page="backing",
            improv_entry_mode="Style Jam Mode",
            improv_intelligence_tab="Entry & Jam",
        )
        session[BACKING_CONTEXT_KEY] = {
            "source": "entry_jam",
            "style": "Bossa Nova",
            "groove": "Bossa nova",
            "display_key": "C",
            "concert_key": "C",
            "entry_mode": "Style Jam Mode",
        }
        req = queue_pending_creative_return_from_backing(session)
        self.assertIsInstance(req, dict)
        st_like = SimpleNamespace(session_state=session, warning=lambda *_a, **_k: None)
        hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertEqual(str(session.get("studio_page") or ""), "creative")
        self.assertIsNone(session.get(PENDING_CREATIVE_RETURN_KEY))

    def test_handle_return_click_sets_creative_before_second_rerun(self) -> None:
        session = _shape_catalog_session(
            studio_page="backing",
            improv_entry_mode="Style Jam Mode",
        )
        session[BACKING_CONTEXT_KEY] = {
            "source": "entry_jam",
            "style": "Bossa Nova",
            "groove": "Bossa nova",
            "display_key": "C",
            "concert_key": "C",
            "entry_mode": "Style Jam Mode",
        }
        st = SimpleNamespace(
            session_state=session,
            warning=lambda *_a, **_k: None,
            rerun=lambda: None,
            stop=lambda: None,
        )
        handle_return_to_creative_click(st, session)
        self.assertEqual(str(session.get("studio_page") or ""), "creative")


class Test8MotifHydrateFromActiveSong(unittest.TestCase):
    def test_motif_hydrate_drops_stale_jam_c_d(self) -> None:
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _shape_catalog_session(
            improv_intelligence_tab="Phrase / Motif",
            display_key="C",
            concert_key="C",
            improv_style_key="C",
            improv_entry_mode="Style Jam Mode",
            improv_generated_sections={"Jam": ["C", "F", "G"]},
        )
        ensure_missions_parent_practice_key_hydrated(session)
        token = str(session.get("display_key") or "")
        self.assertNotEqual(token, "C")
        self.assertIn(token, {"Am", "Bm", "A", "B"})
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))


class Test9MotifTransformInvariants(unittest.TestCase):
    def _seed(self) -> dict:
        return {
            "chord": "Dm",
            "notes": ["D", "F", "A", "C"],
            "midi": [62, 65, 69, 72],
            "rhythm": "♩ ♩ ♩ ♩",
            "rhythm_key": "quarter-quarter-quarter",
            "rhythm_symbols": ["♩", "♩", "♩", "♩"],
        }

    def test_ascending_monotonic_no_lower_octave_restart(self) -> None:
        pat = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="diatonic", direction="ascending", length=8
        )
        midis = [int(m) for m in pat["midi"]]
        cell = 4
        for i in range(1, 8):
            prev = midis[(i - 1) * cell : i * cell]
            cur = midis[i * cell : (i + 1) * cell]
            for a, b in zip(prev, cur):
                self.assertGreaterEqual(b, a)
            self.assertGreater(min(cur), min(prev) - 1)

    def test_descending_monotonic(self) -> None:
        pat = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="diatonic", direction="descending", length=8
        )
        midis = [int(m) for m in pat["midi"]]
        cell = 4
        for i in range(1, 8):
            prev = midis[(i - 1) * cell : i * cell]
            cur = midis[i * cell : (i + 1) * cell]
            for a, b in zip(prev, cur):
                self.assertLessEqual(b, a)

    def test_repeated_cells_same_rule_and_deterministic(self) -> None:
        a = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="thirds", direction="ascending", length=8
        )
        b = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="thirds", direction="ascending", length=8
        )
        self.assertEqual(a["notes"], b["notes"])
        self.assertEqual(a["midi"], b["midi"])
        self.assertEqual(a["cells"][0], ["D", "F", "A", "C"])
        cell_len = 4
        # Later cells are collection-step transpositions of the same base motif,
        # not independently generated material.
        self.assertEqual(len(a["cells"]), 8)
        for cell in a["cells"][1:]:
            self.assertEqual(len(cell), cell_len)
        means = [
            sum(int(m) for m in a["midi"][i * cell_len : (i + 1) * cell_len]) / cell_len
            for i in range(8)
        ]
        for i in range(1, 8):
            self.assertGreater(means[i], means[i - 1] - 0.01)

    def test_sequence_up_down_preserves_intervals_and_rhythm(self) -> None:
        seed = self._seed()
        up = transform_motif(seed, "sequence_up", key_center="Dm")
        down = transform_motif(up, "sequence_down", key_center="Dm")
        self.assertEqual(len(up["notes"]), 4)
        self.assertEqual(up.get("rhythm_symbols"), seed["rhythm_symbols"])
        src = [int(m) for m in seed["midi"]]
        up_m = [int(m) for m in up["midi"]]
        self.assertEqual(len(up_m), len(src))
        self.assertNotEqual(up_m, src)
        # Diatonic sequence: each pitch moves one collection step; contour sign is preserved.
        self.assertTrue(all(b >= a for a, b in zip(src, up_m)))
        self.assertEqual([int(m) % 12 for m in down["midi"]], [int(m) % 12 for m in src])

    def test_invert_around_first_note_not_reverse(self) -> None:
        seed = self._seed()
        inv = transform_motif(seed, "invert", key_center="Dm")
        self.assertNotEqual(inv["notes"], list(reversed(seed["notes"])))
        self.assertEqual(len(inv["notes"]), 4)
        self.assertEqual(inv.get("rhythm_symbols"), seed["rhythm_symbols"])
        pivot = seed["midi"][0]
        expected = [2 * pivot - m for m in seed["midi"]]
        self.assertEqual([int(m) for m in inv["midi"]], expected)
        again = transform_motif(inv, "invert", key_center="Dm")
        self.assertEqual([int(m) for m in again["midi"]], seed["midi"])

    def test_text_notation_playback_agree(self) -> None:
        pat = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="diatonic", direction="ascending", length=8
        )
        abc = build_motif_abc(pat, key_center="Dm", bpm=100)
        self.assertIn("K:d", abc.replace("K:Dm", "K:d"))
        self.assertEqual(len(pat["notes"]), len(pat["midi"]))
        self.assertNotIn("K:D\n", abc)


class Test10EnharmonicAndSignatures(unittest.TestCase):
    def test_gm_spells_bb_even_under_stale_d_major(self) -> None:
        self.assertEqual(harmonic_reference_for_chord("Gm", song_display_key="D"), "Gm")
        motif = apply_motif_chord_spelling(
            {"chord": "Gm", "notes": ["G", "A#", "D"], "midi": [67, 70, 74]},
            "Gm",
            song_display_key="D",
        )
        joined = " ".join(motif["notes"])
        self.assertIn("Bb", joined)
        self.assertNotIn("A#", joined)
        generated = generate_motif_for_chord("Gm", key_center="Gm", level="Beginner")
        self.assertNotIn("A#", " ".join(generated.get("notes") or []))

    def test_key_headers_match_mode(self) -> None:
        self.assertEqual(_abc_key_header("Dm"), "d")
        self.assertEqual(_abc_key_header("C#m"), "C#m")
        self.assertEqual(_abc_key_header("Eb"), "Eb")
        self.assertEqual(_abc_key_header("Ebm"), "Ebm")


class Test11MissionChordDoesNotMutateGlobalKey(unittest.TestCase):
    def test_multi_chord_selection_keeps_practice_key(self) -> None:
        from music_workflow_mutation import mutate_mission_chord_selection

        session = _shape_catalog_session(
            improv_intelligence_tab="Missions",
            display_key="Am",
            concert_key="Am",
            improv_active_mission="Outline chord tones",
        )
        for chord, idx in (("C#m", 0), ("A", 1), ("F#m", 2), ("C#m", 0)):
            mutate_mission_chord_selection(
                session,
                chord=chord,
                section="Verse",
                chord_index=idx,
                chord_label=f"Verse · {chord}",
            )
            self.assertEqual(str(session.get("display_key") or ""), "Am", chord)
            self.assertEqual(str(session.get("concert_key") or ""), "Am", chord)
            self.assertEqual(get_practice_concert_key(session, SHAPE), "Am")


class Test12SourceRecordIsolation(unittest.TestCase):
    def test_catalog_and_custom_sticky_keys_do_not_cross_write(self) -> None:
        session = _shape_catalog_session(
            sbi_preview_source="Custom progression",
            improv_song_source="Custom progression",
            improv_intelligence_tab="Entry & Jam",
            display_key="Eb",
        )
        write = resolve_settings_pick_for_write(session)
        self.assertTrue(str(write).startswith("custom::"), write)
        set_practice_concert_key(session, "Eb")
        self.assertEqual(get_practice_concert_key(session, SHAPE), "Am")
        self.assertEqual(get_practice_concert_key(session, write), "Eb")

        session["improv_intelligence_tab"] = "Missions"
        session["sbi_preview_source"] = "Custom progression"
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))
        write_m = resolve_settings_pick_for_write(session)
        self.assertFalse(str(write_m).startswith("custom::"), write_m)

    def test_sidebar_owner_flips_with_explicit_source_not_leftover_preview(self) -> None:
        session = _shape_catalog_session(
            sbi_preview_source="Custom progression",
            improv_intelligence_tab="Missions",
        )
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))
        session["improv_intelligence_tab"] = "Entry & Jam"
        session["improv_entry_mode"] = "Song-Based Improvisation"
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))
        session["sbi_preview_source"] = "Active song"
        session["improv_song_source"] = "Active song"
        self.assertFalse(custom_sbi_owns_sidebar_practice_key(session))


if __name__ == "__main__":
    unittest.main()
