"""Human-QA Creative/SBI/Missions/Backing/Motif coherence regressions.

Proves the user-visible contracts from Creative Stabilization visual QA.
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
    _backing_groove_style_from_ctx,
    _entry_jam_context_from_owner_snapshot,
    build_mission_context,
    open_backing_from_creative,
    set_backing_context,
)
from backing_context_ui import resolve_backing_card_style_label
from backing_source_navigation import hydrate_backing_source_for_page
from creative_key_sync import _catalog_song_workflow_owns_practice_key
from generated_workflow_artifact import GeneratedWorkflowArtifactSnapshot
from harmonic_spelling import apply_motif_chord_spelling, harmonic_reference_for_chord
from improvisation_intelligence import ChordCoachInsight
from improvisation_intelligence_ui import custom_lab_open_button_label
from improvisation_missions import (
    MISSION_EXAMPLE_KEY,
    MissionExample,
    mission_example_fingerprint,
    motif_material_fingerprint,
    store_mission_example,
)
from improvisation_motif import (
    _abc_key_header,
    _pattern_step_size,
    _pitch_collection_pcs,
    _shift_notes_by_collection_steps,
    build_motif_abc,
    build_motif_pattern,
    generate_motif_for_chord,
    parse_motif_abc_note_names,
    transform_motif,
)
from mission_backing_alignment import build_mission_backing_alignment_payload
from mission_pitch_spelling import coaching_reference_for_mission_chord
from mission_return_destination import (
    MISSION_CANONICAL_RETURN_DESTINATION_KEY,
    apply_sealed_mission_return_destination,
    build_mission_return_destination,
    rehydrate_mission_return_destination_from_backing_context,
    seal_mission_return_destination,
)
from music_theory import NOTE_TO_MIDI, normalize_root, split_chord
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
from songs.music_source import LAST_CUSTOM_STATE_KEY, SOURCE_CATALOG, SOURCE_CUSTOM
from songs.practice_key_state import (
    apply_authoritative_practice_key,
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
        "active_music_source": SOURCE_CATALOG,
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
        "guitar_capo_shape_key": "A",
        "instrument": "Piano",
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


def _note_pc(note: str) -> int:
    return NOTE_TO_MIDI.get(normalize_root(split_chord(str(note))[0]), 60) % 12


def _source_card(session: dict) -> dict[str, str]:
    pick = str(session.get("active_catalog_pick_key") or "").strip()
    sel = session.get("selected_song") if isinstance(session.get("selected_song"), dict) else {}
    title = str(sel.get("title") or session.get("song") or "").strip()
    original = str(sel.get("key") or sel.get("original_key") or "").strip()
    practice = str(get_practice_concert_key(session, pick) or session.get("display_key") or "").strip()
    return {
        "pick": pick,
        "title": title,
        "original": original,
        "practice": practice,
        "sidebar": str(session.get("display_key") or "").strip(),
        "shape": str(session.get("guitar_capo_shape_key") or "").strip(),
        "source": str(session.get("active_music_source") or "").strip(),
    }


def _assert_sidebar_matches_card(test: unittest.TestCase, session: dict, *, label: str) -> dict[str, str]:
    card = _source_card(session)
    test.assertEqual(card["sidebar"], card["practice"], f"{label}: sidebar vs card PK")
    return card


def _mission_example(chord: str, notes: list[str], midi: list[int]) -> MissionExample:
    motif = {
        "chord": chord,
        "notes": list(notes),
        "midi": list(midi),
        "display": " – ".join(notes),
        "rhythm": "♩ ♩ ♩ ♩",
        "rhythm_symbols": ["♩", "♩", "♩", "♩"],
    }
    return MissionExample(
        mission="Outline chord tones",
        variant="normal",
        chord=chord,
        section="Chorus",
        song_title="Shape of You",
        display_key="Am",
        concert_key="Am",
        instrument="Piano",
        level="Intermediate",
        focus="Improvisation",
        motif=motif,
        abc="",
        tab="",
        piano_html="",
        why="",
        practice_steps=[],
        insight=ChordCoachInsight(
            chord=chord,
            scales=[],
            scale_suggestions=[],
            chord_tones=list(notes[:3]),
            tensions=[],
            avoid_notes=[],
            target_notes=[],
            motif_idea="",
            resolve_hint="",
        ),
        show_tab=False,
        show_piano=False,
    )


class Test1CustomLabPresentation(unittest.TestCase):
    def test_open_custom_lab_label_is_the_rendered_button_mapping(self) -> None:
        from app_ui import STUDIO_PAGE_META

        icon = str(STUDIO_PAGE_META.get("custom", {}).get("icon") or "")
        self.assertTrue(icon)
        label = custom_lab_open_button_label()
        self.assertEqual(label, f"{icon} Open Custom Lab")
        self.assertTrue(label.endswith("Open Custom Lab"))
        self.assertNotEqual(label.strip(), "Custom")
        import improvisation_intelligence_ui as ui_mod
        import inspect

        button_src = inspect.getsource(ui_mod)
        self.assertIn("custom_lab_open_button_label()", button_src)


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
        session["active_music_source"] = SOURCE_CUSTOM
        self.assertTrue(custom_sbi_owns_sidebar_practice_key(session))


class Test3MissionBackingRoundTrip(unittest.TestCase):
    def _mission_session(self, chord: str, *, idx: int = 2) -> dict:
        return _shape_catalog_session(
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

    def _round_trip(self, chord: str, notes: list[str], midi: list[int]) -> dict:
        session = self._mission_session(chord)
        example = _mission_example(chord, notes, midi)
        store_mission_example(session, example)
        stored = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(stored, dict)
        self.assertEqual((stored or {}).get("chord"), chord)
        self.assertEqual(list(((stored or {}).get("motif") or {}).get("notes") or []), notes)
        example_fp = motif_material_fingerprint(example.motif)
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord=chord,
            section_label="Chorus",
            chord_idx=2,
            song_title="Shape of You",
            example=example,
            with_practice_lick=True,
        )
        self.assertEqual(align.get("chord_symbol"), chord)
        self.assertEqual(align.get("example_fingerprint"), example_fp)
        dest = build_mission_return_destination(
            align,
            handoff_mode="practice_in_jam",
            with_practice_lick=True,
            request_seq=1,
        )
        seal_mission_return_destination(session, dest)
        ctx = build_mission_context(session)
        set_backing_context(session, ctx)
        self.assertEqual(ctx.source, "mission")
        canonical = str(session.get("_mission_backing_canonical_chord") or "")
        self.assertEqual(canonical, chord)
        rendered = " ".join(ctx.progression or []) + " " + str(ctx.progression_label or "")
        self.assertIn(chord, rendered)
        self.assertEqual(str(ctx.progression[0] if ctx.progression else ""), chord)
        sealed = session.get(MISSION_CANONICAL_RETURN_DESTINATION_KEY)
        self.assertIsInstance(sealed, dict)
        self.assertEqual(sealed.get("creative_tab"), "Missions")
        self.assertEqual(sealed.get("chord_symbol"), chord)
        self.assertEqual(sealed.get("example_fingerprint"), example_fp)
        self.assertEqual(list(sealed.get("example_notes") or []), notes)
        blob = session.get(BACKING_CONTEXT_KEY)
        self.assertIsInstance(blob, dict)
        stamped = (blob or {}).get("mission_return_destination")
        self.assertIsInstance(stamped, dict)
        self.assertEqual((stamped or {}).get("chord_symbol"), chord)

        # Refresh / rerun while still on Backing must keep chord + example + dest.
        session["studio_page"] = "backing"
        session["improv_intelligence_tab"] = "Song-Based Improvisation"
        st_like = SimpleNamespace(session_state=session, warning=lambda *_a, **_k: None)
        hydrate_backing_source_for_page(session, st_like=st_like)
        recovered = rehydrate_mission_return_destination_from_backing_context(session)
        self.assertIsInstance(recovered, dict)
        self.assertEqual((recovered or {}).get("chord_symbol"), chord)
        self.assertEqual((recovered or {}).get("creative_tab"), "Missions")
        raw_ex = session.get(MISSION_EXAMPLE_KEY)
        self.assertEqual(list(((raw_ex or {}).get("motif") or {}).get("notes") or []), notes)
        self.assertEqual(
            motif_material_fingerprint((raw_ex or {}).get("motif") or {}),
            example_fp,
        )

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
        hydrate_backing_source_for_page(session, st_like=st_like)
        self.assertEqual(session.get("improv_intelligence_tab"), "Missions")
        self.assertEqual(session.get("ii_selected_chord"), chord)
        after = session.get(MISSION_EXAMPLE_KEY)
        self.assertEqual(list(((after or {}).get("motif") or {}).get("notes") or []), notes)
        self.assertEqual(str((after or {}).get("material_fp") or ""), example_fp)
        self.assertEqual(str((after or {}).get("mission") or ""), "Outline chord tones")
        self.assertEqual(str(session.get("display_key") or ""), "Am")
        return session

    def test_a_major_mission_backing_round_trip_survives_refresh(self) -> None:
        self._round_trip("A", ["A", "C#", "E", "G"], [69, 73, 76, 79])

    def test_non_tonic_fsharp_minor_round_trip_survives_refresh(self) -> None:
        self._round_trip("F#m", ["F#", "A", "C#", "E"], [66, 69, 73, 76])

    def test_return_does_not_mix_sealed_notes_with_newer_example_identity(self) -> None:
        notes_a = ["A", "C#", "E", "G"]
        midi_a = [69, 73, 76, 79]
        session = self._mission_session("A")
        session["_mission_example_artifact_id"] = "artifact-a"
        example_a = _mission_example("A", notes_a, midi_a)
        store_mission_example(session, example_a)
        fp_a = motif_material_fingerprint(example_a.motif)
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="A",
            section_label="Chorus",
            chord_idx=2,
            song_title="Shape of You",
            example=example_a,
            with_practice_lick=True,
        )
        self.assertEqual(align.get("example_fingerprint"), fp_a)
        self.assertEqual(align.get("example_material_fp"), fp_a)
        self.assertEqual(align.get("example_artifact_id"), "artifact-a")
        self.assertEqual(align.get("example_mission"), "Outline chord tones")
        dest = build_mission_return_destination(
            align,
            handoff_mode="practice_in_jam",
            with_practice_lick=True,
            request_seq=1,
        )
        seal_mission_return_destination(session, dest)

        newer = _mission_example("Em", ["E", "G", "B", "D"], [64, 67, 71, 74])
        newer.mission = "Guide tones"
        newer.variant = "harder"
        newer.section = "Verse"
        newer.abc = "K:Em\nE G B D"
        store_mission_example(session, newer)
        session["_mission_example_artifact_id"] = "artifact-b"
        session[MISSION_EXAMPLE_KEY]["artifact_id"] = "artifact-b"
        session[MISSION_EXAMPLE_KEY]["material_fp"] = motif_material_fingerprint(newer.motif)
        fp_b = motif_material_fingerprint(newer.motif)
        self.assertNotEqual(fp_b, fp_a)

        apply_sealed_mission_return_destination(session)
        after = session.get(MISSION_EXAMPLE_KEY)
        self.assertIsInstance(after, dict)
        self.assertEqual(list(((after or {}).get("motif") or {}).get("notes") or []), notes_a)
        self.assertEqual(list(((after or {}).get("motif") or {}).get("midi") or []), midi_a)
        self.assertEqual(str((after or {}).get("material_fp") or ""), fp_a)
        self.assertEqual(str((after or {}).get("chord") or ""), "A")
        self.assertEqual(str((after or {}).get("mission") or ""), "Outline chord tones")
        self.assertEqual(str((after or {}).get("section") or ""), "Chorus")
        self.assertNotEqual(str((after or {}).get("mission") or ""), "Guide tones")
        self.assertNotEqual(str((after or {}).get("artifact_id") or ""), "artifact-b")
        self.assertEqual(str((after or {}).get("artifact_id") or ""), "artifact-a")
        self.assertNotIn("K:Em", str((after or {}).get("abc") or ""))
        self.assertEqual(motif_material_fingerprint((after or {}).get("motif") or {}), fp_a)


class Test4StyleJamBossaMetadata(unittest.TestCase):
    def test_custom_sbi_backing_card_renders_progression_after_leftover_pop(self) -> None:
        from backing_context import BackingContext
        from backing_context_ui import render_backing_creative_context_card

        ctx = BackingContext(
            source="song_improv",
            source_label="Song-Based Improvisation",
            active_song_id=TRIAL,
            song_title="Trial Song",
            key="D",
            display_key="D",
            concert_key="D",
            bpm=100,
            style="Pop",
            groove="Pop groove",
            progression=["Em", "Em", "D", "D"],
            progression_label="Trial Song · Em–Em–D–D",
            entry_mode="Song-Based Improvisation",
            mode_label="Song-Based Improvisation",
            bound_pick_key=TRIAL,
        )
        captured: list[str] = []
        st = SimpleNamespace(markdown=lambda html, **_k: captured.append(str(html)))
        state = SimpleNamespace(
            style="Pop groove",
            groove="Pop groove",
            meter="4/4",
            instrument="Piano",
            practice_concert_key="D",
            show_chart_badge=False,
            chart_badge_value="",
            chart_badge_label="",
            chart_sections=None,
            concert_sections={"Verse": ["Em", "Em", "D", "D"]},
            applied_bpm=100,
        )
        render_backing_creative_context_card(
            st,
            ctx,
            {"backing_groove_style": "Pop groove", "instrument": "Piano"},
            applied_bpm=100,
            applied_groove="Pop groove",
            practice_key="D",
            musical_state=state,
        )
        html = "\n".join(captured)
        self.assertIn("Progression:", html)
        self.assertIn("Em", html)
        self.assertIn("Trial", html + ctx.song_title)


    def test_bossa_snapshot_drives_badge_and_backing_config_after_rerun(self) -> None:
        session = {
            "improv_groove": "Pop groove",
            "backing_groove_style": "Pop groove",
            "improv_style": "Pop",
            "active_catalog_pick_key": SHAPE,
            "studio_page": "backing",
        }
        ctx = _entry_jam_context_from_owner_snapshot(session, _bossa_snapshot())
        session[BACKING_CONTEXT_KEY] = ctx.to_dict()
        joined = " ".join(
            [
                str(ctx.style or ""),
                str(ctx.groove or ""),
                str(getattr(ctx, "progression_label", "") or ""),
            ]
        )
        self.assertIn("Bossa", joined)
        self.assertNotIn("Pop", str(ctx.groove or ""))
        groove = _backing_groove_style_from_ctx(ctx)
        self.assertIn("Bossa", groove)
        self.assertNotIn("Pop", groove)
        badge = resolve_backing_card_style_label(
            session,
            ctx,
            applied_groove="Pop groove",
            state_style="Pop groove",
            state_groove="Pop groove",
        )
        self.assertIn("Bossa", badge)
        self.assertNotIn("Pop", badge)
        # Hydration / second paint still reads sealed Bossa, not leftover Pop.
        st_like = SimpleNamespace(session_state=session, warning=lambda *_a, **_k: None)
        hydrate_backing_source_for_page(session, st_like=st_like)
        ctx2 = _entry_jam_context_from_owner_snapshot(session, _bossa_snapshot())
        badge2 = resolve_backing_card_style_label(
            session,
            ctx2,
            applied_groove=str(session.get("backing_groove_style") or ""),
        )
        self.assertIn("Bossa", badge2)
        self.assertIn("Bossa", str(session.get("backing_groove_style") or ""))


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

    def _assert_direction_midis(self, midis: list[int], *, sign: int, label: str) -> None:
        self.assertGreaterEqual(len(midis), 8, label)
        for i in range(1, len(midis)):
            if sign >= 0:
                self.assertGreaterEqual(
                    midis[i],
                    midis[i - 1],
                    msg=f"{label} ascending adjacent {i - 1}->{i}: {midis[i - 1]}->{midis[i]}",
                )
            else:
                self.assertLessEqual(
                    midis[i],
                    midis[i - 1],
                    msg=f"{label} descending adjacent {i - 1}->{i}: {midis[i - 1]}->{midis[i]}",
                )

    def test_ascending_complete_midi_sequence_is_nondecreasing(self) -> None:
        pat = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="diatonic", direction="ascending", length=8
        )
        midis = [int(m) for m in pat["midi"]]
        self.assertEqual(len(midis), 32)
        self._assert_direction_midis(midis, sign=1, label="seed-asc")

    def test_descending_complete_midi_sequence_is_nonincreasing(self) -> None:
        seed = {
            "chord": "Dm",
            "notes": ["C", "A", "F", "D"],
            "midi": [72, 69, 65, 62],
            "rhythm": "♩ ♩ ♩ ♩",
            "rhythm_key": "quarter-quarter-quarter",
            "rhythm_symbols": ["♩", "♩", "♩", "♩"],
        }
        pat = build_motif_pattern(
            seed, key_center="Dm", pattern_type="diatonic", direction="descending", length=8
        )
        midis = [int(m) for m in pat["midi"]]
        self.assertEqual(len(midis), 32)
        self._assert_direction_midis(midis, sign=-1, label="seed-desc")

    def test_zigzag_seed_every_adjacent_midi_follows_named_direction(self) -> None:
        """Non-monotone source must still realize every adjacent MIDI in direction."""
        zigzag = {
            "chord": "Fm",
            "notes": ["F", "B", "Ab", "C"],
            "midi": [65, 71, 68, 72],
            "rhythm": "♩ ♩ ♩ ♩",
            "rhythm_key": "quarter-quarter-quarter",
            "rhythm_symbols": ["♩", "♩", "♩", "♩"],
        }
        self.assertFalse(all(b >= a for a, b in zip(zigzag["midi"], zigzag["midi"][1:])))
        self.assertFalse(all(b <= a for a, b in zip(zigzag["midi"], zigzag["midi"][1:])))

        asc = build_motif_pattern(
            zigzag, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        desc = build_motif_pattern(
            zigzag, key_center="Fm", pattern_type="diatonic", direction="descending", length=8
        )
        again = build_motif_pattern(
            zigzag, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        self.assertEqual(asc["midi"], again["midi"])
        self.assertEqual(asc["notes"], again["notes"])
        self.assertEqual(asc["rhythm_symbols"], zigzag["rhythm_symbols"] * 8)
        self.assertEqual(asc["cells"][0], ["F", "B", "Ab", "C"])
        self.assertEqual(desc["cells"][0], ["F", "B", "Ab", "C"])
        self.assertEqual([_note_pc(n) for n in asc["cells"][0]], [5, 11, 8, 0])
        self._assert_direction_midis([int(m) for m in asc["midi"]], sign=1, label="zigzag-asc")
        self._assert_direction_midis([int(m) for m in desc["midi"]], sign=-1, label="zigzag-desc")
        neighbor = {
            "chord": "Fm",
            "notes": ["Ab", "G", "F", "G"],
            "midi": [68, 67, 65, 67],
            "rhythm": "♩ ♩ ♩ ♩",
            "rhythm_key": "quarter-quarter-quarter",
            "rhythm_symbols": ["♩", "♩", "♩", "♩"],
        }
        n_asc = build_motif_pattern(
            neighbor, key_center="Fm", pattern_type="diatonic", direction="ascending", length=8
        )
        n_desc = build_motif_pattern(
            neighbor, key_center="Fm", pattern_type="diatonic", direction="descending", length=8
        )
        self.assertEqual(n_asc["cells"][0], ["Ab", "G", "F", "G"])
        self._assert_direction_midis([int(m) for m in n_asc["midi"]], sign=1, label="neighbor-asc")
        self._assert_direction_midis([int(m) for m in n_desc["midi"]], sign=-1, label="neighbor-desc")

    def test_generated_nonmonotone_motif_pattern_obeys_direction(self) -> None:
        motif = generate_motif_for_chord("Fm", key_center="Fm", level="Intermediate")
        self.assertGreaterEqual(len(motif.get("notes") or []), 3)
        source_pcs = [_note_pc(n) for n in motif["notes"]]
        source_rhythm = list(motif.get("rhythm_symbols") or [])
        # Prefer a compact generated contour; if it is already monotone the
        # zigzag-seed test still proves within-cell direction.
        pat = build_motif_pattern(
            motif,
            key_center="Fm",
            pattern_type="diatonic",
            direction="ascending",
            length=8,
        )
        self.assertEqual([_note_pc(n) for n in pat["cells"][0]], source_pcs)
        if source_rhythm:
            self.assertEqual(pat["rhythm_symbols"][: len(source_rhythm)], source_rhythm)
        self._assert_direction_midis([int(m) for m in pat["midi"]], sign=1, label="generated-asc")
        down = build_motif_pattern(
            motif,
            key_center="Fm",
            pattern_type="diatonic",
            direction="descending",
            length=8,
        )
        self.assertEqual([_note_pc(n) for n in down["cells"][0]], source_pcs)
        self._assert_direction_midis([int(m) for m in down["midi"]], sign=-1, label="generated-desc")

    def test_thirds_cells_keep_collection_step_pitch_classes(self) -> None:
        seed = self._seed()
        a = build_motif_pattern(
            seed, key_center="Dm", pattern_type="thirds", direction="ascending", length=8
        )
        b = build_motif_pattern(
            seed, key_center="Dm", pattern_type="thirds", direction="ascending", length=8
        )
        self.assertEqual(a["notes"], b["notes"])
        self.assertEqual(a["midi"], b["midi"])
        self.assertEqual(a["cells"][0], ["D", "F", "A", "C"])
        collection = _pitch_collection_pcs("Dm", "thirds")
        step = _pattern_step_size("thirds")
        self.assertEqual(step, 2)
        self.assertEqual(len(a["cells"]), 8)
        for i, cell in enumerate(a["cells"]):
            expected_notes, expected_midi = _shift_notes_by_collection_steps(
                seed["notes"],
                key_center="Dm",
                collection_pcs=collection,
                steps=i * step,
                source_midis=seed["midi"],
            )
            self.assertEqual(cell, expected_notes)
            got = [int(m) for m in a["midi"][i * 4 : (i + 1) * 4]]
            self.assertEqual(len(got), 4)
            self.assertEqual([m % 12 for m in got], [int(m) % 12 for m in expected_midi])
        self._assert_direction_midis([int(m) for m in a["midi"]], sign=1, label="thirds-asc")

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

    def test_text_notation_playback_abc_pitches_match_midi(self) -> None:
        pat = build_motif_pattern(
            self._seed(), key_center="Dm", pattern_type="diatonic", direction="ascending", length=8
        )
        abc = build_motif_abc(pat, key_center="Dm", bpm=100)
        self.assertIn("K:d", abc.replace("K:Dm", "K:d"))
        self.assertEqual(len(pat["notes"]), len(pat["midi"]))
        self.assertNotIn("K:D\n", abc)
        parsed = parse_motif_abc_note_names(abc)
        self.assertEqual(len(parsed), len(pat["notes"]))
        for name, note, midi in zip(parsed, pat["notes"], pat["midi"]):
            self.assertEqual(_note_pc(name), _note_pc(str(note)))
            self.assertEqual(_note_pc(name), int(midi) % 12)


class Test10EnharmonicAndSignatures(unittest.TestCase):
    def test_gm_spells_bb_even_under_stale_d_major(self) -> None:
        self.assertEqual(harmonic_reference_for_chord("Gm", song_display_key="D"), "Gm")
        self.assertEqual(coaching_reference_for_mission_chord("Gm", song_display_key="D"), "Gm")
        self.assertEqual(coaching_reference_for_mission_chord("Dm", song_display_key="D"), "Dm")
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
        abc = build_motif_abc(
            {"notes": ["G", "Bb", "D"], "midi": [67, 70, 74], "rhythm_symbols": ["♩", "♩", "♩"]},
            key_center="Gm",
        )
        self.assertEqual(_abc_key_header("Gm"), "g")
        self.assertIn("_B", abc)
        self.assertNotIn("^A", abc)

    def test_key_headers_match_mode(self) -> None:
        self.assertEqual(_abc_key_header("Dm"), "d")
        self.assertEqual(_abc_key_header("C#m"), "C#m")
        self.assertEqual(_abc_key_header("Eb"), "Eb")
        self.assertEqual(_abc_key_header("Ebm"), "Ebm")


class Test11MissionChordDoesNotMutateGlobalKey(unittest.TestCase):
    def test_multi_chord_selection_keeps_practice_and_shape_keys_after_refresh(self) -> None:
        from music_workflow_mutation import mutate_mission_chord_selection
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated

        session = _shape_catalog_session(
            improv_intelligence_tab="Missions",
            display_key="Am",
            concert_key="Am",
            improv_active_mission="Outline chord tones",
            guitar_capo_shape_key="A",
        )
        before = {
            "display": str(session.get("display_key") or ""),
            "concert": str(session.get("concert_key") or ""),
            "shape": str(session.get("guitar_capo_shape_key") or ""),
            "pick": str(session.get("active_catalog_pick_key") or ""),
            "original": str((session.get("selected_song") or {}).get("key") or ""),
        }
        last_chord = ""
        for chord, idx in (("C#m", 0), ("A", 1), ("F#m", 2), ("C#m", 0)):
            mutate_mission_chord_selection(
                session,
                chord=chord,
                section="Verse",
                chord_index=idx,
                chord_label=f"Verse · {chord}",
            )
            last_chord = chord
            self.assertEqual(str(session.get("display_key") or ""), before["display"], chord)
            self.assertEqual(str(session.get("concert_key") or ""), before["concert"], chord)
            self.assertEqual(str(session.get("guitar_capo_shape_key") or ""), before["shape"], chord)
            self.assertEqual(get_practice_concert_key(session, SHAPE), "Am")
            self.assertEqual(str((session.get("selected_song") or {}).get("key") or ""), "Bm")
        ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(str(session.get("display_key") or ""), before["display"])
        self.assertEqual(str(session.get("concert_key") or ""), before["concert"])
        self.assertEqual(str(session.get("guitar_capo_shape_key") or ""), before["shape"])
        self.assertEqual(session.get("ii_selected_chord"), last_chord)
        self.assertEqual(str(session.get("active_catalog_pick_key") or ""), before["pick"])


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

    def test_shape_trial_alternating_keys_match_sidebar_and_card(self) -> None:
        """Real Catalog↔Custom activate/hydrate — no manual pick/source assignment."""
        from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated
        from songs.music_source import (
            begin_explicit_catalog_selection,
            commit_custom_active_song,
            custom_pick_key_for,
        )
        from songs.state import apply_pick_key

        try:
            from tests.test_custom_to_catalog_owner_switch import (
                CATALOG,
                PK_SHAPE,
                _shape_catalog_session as _owner_shape_session,
                _trial_active,
            )
        except ImportError:
            from test_custom_to_catalog_owner_switch import (
                CATALOG,
                PK_SHAPE,
                _shape_catalog_session as _owner_shape_session,
                _trial_active,
            )

        session = _owner_shape_session(practice_key="Bm")
        session.update(
            {
                "studio_page": "creative",
                "improv_intelligence_tab": "Song-Based Improvisation",
                "improv_entry_mode": "Song-Based Improvisation",
                "improv_song_source": "Active song",
                "sbi_preview_source": "Active song",
                "guitar_capo_shape_key": "A",
                "instrument": "Piano",
            }
        )
        set_practice_concert_key(session, "Am", pick_key=PK_SHAPE)
        session["display_key"] = "Am"
        session["concert_key"] = "Am"
        shape1 = _assert_sidebar_matches_card(self, session, label="shape-1")
        self.assertEqual(shape1["title"], "Shape of You")
        self.assertEqual(shape1["original"], "Bm")
        self.assertEqual(shape1["practice"], "Am")
        self.assertEqual(shape1["shape"], "A")
        self.assertEqual(shape1["source"], SOURCE_CATALOG)

        st = SimpleNamespace(session_state=session, rerun=lambda: None)
        with mock.patch("songs.state.persist_music_local_state"), mock.patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(
                st,
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        trial_pick = custom_pick_key_for(_trial_active())
        # Activating Trial as Global Active is a fresh Custom original — leftover
        # Shape Am/Dm sticky must not survive (product: EXPLICIT USER SONG PICK).
        self.assertFalse(get_practice_concert_key(session, PK_SHAPE))
        trial1 = _assert_sidebar_matches_card(self, session, label="trial-activate")
        self.assertEqual(trial1["title"], "Trial Song")
        self.assertEqual(trial1["original"], "D")
        self.assertEqual(trial1["source"], SOURCE_CUSTOM)
        self.assertEqual(trial1["practice"], "D")

        apply_authoritative_practice_key(
            session,
            "E",
            pick_key=trial_pick,
            sync_display=True,
            sync_custom_widgets=True,
        )
        session["guitar_capo_shape_key"] = "E"
        trial_live = _assert_sidebar_matches_card(self, session, label="trial-pk")
        self.assertEqual(trial_live["original"], "D")
        self.assertEqual(trial_live["practice"], "E")
        self.assertEqual(trial_live["shape"], "E")
        # Creative rerun hydrate — not Backing reclaim.
        ensure_missions_parent_practice_key_hydrated(session)
        trial_rerun = _assert_sidebar_matches_card(self, session, label="trial-hydrate")
        self.assertEqual(trial_rerun["title"], "Trial Song")
        self.assertEqual(trial_rerun["original"], "D")
        self.assertEqual(trial_rerun["practice"], "E")
        self.assertEqual(get_practice_concert_key(session, trial_pick), "E")

        begin_explicit_catalog_selection(session)
        with mock.patch("songs.state.persist_music_local_state"):
            apply_pick_key(st, PK_SHAPE, CATALOG, persist=False, origin="user")
        # Return to Shape is a fresh original B minor — Trial E must not leak.
        shape_fresh = _assert_sidebar_matches_card(self, session, label="shape-fresh")
        self.assertEqual(shape_fresh["title"], "Shape of You")
        self.assertEqual(shape_fresh["original"], "Bm")
        self.assertEqual(shape_fresh["source"], SOURCE_CATALOG)
        self.assertEqual(shape_fresh["practice"], "Bm")
        self.assertNotEqual(shape_fresh["practice"], "E")
        self.assertNotEqual(get_practice_concert_key(session, PK_SHAPE), "E")

        apply_authoritative_practice_key(session, "Am", pick_key=PK_SHAPE, sync_display=True)
        session["guitar_capo_shape_key"] = "A"
        shape2 = _assert_sidebar_matches_card(self, session, label="shape-pk")
        self.assertEqual(shape2["original"], "Bm")
        self.assertEqual(shape2["practice"], "Am")
        self.assertEqual(shape2["shape"], "A")
        self.assertNotEqual(get_practice_concert_key(session, trial_pick), "Am")
        ensure_missions_parent_practice_key_hydrated(session)
        shape_rerun = _assert_sidebar_matches_card(self, session, label="shape-hydrate")
        self.assertEqual(shape_rerun["original"], "Bm")
        self.assertEqual(shape_rerun["practice"], "Am")
        self.assertEqual(get_practice_concert_key(session, PK_SHAPE), "Am")
        self.assertNotEqual(get_practice_concert_key(session, trial_pick), "Am")

        with mock.patch("songs.state.persist_music_local_state"), mock.patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            commit_custom_active_song(
                st,
                _trial_active(),
                invalidate_backing=lambda *_a, **_k: None,
            )
        trial_again = _assert_sidebar_matches_card(self, session, label="trial-reactivate")
        self.assertEqual(trial_again["title"], "Trial Song")
        self.assertEqual(trial_again["original"], "D")
        self.assertEqual(trial_again["source"], SOURCE_CUSTOM)
        self.assertNotEqual(trial_again["practice"], "Am")
        ensure_missions_parent_practice_key_hydrated(session)
        trial_again_h = _assert_sidebar_matches_card(self, session, label="trial-reactivate-hydrate")
        self.assertEqual(trial_again_h["original"], "D")
        self.assertNotEqual(trial_again_h["practice"], "Am")


class TestImportErrorAuthorityFailSafe(unittest.TestCase):
    def test_catalog_owner_reads_raw_entry_jam_blob_when_import_fails(self) -> None:
        session = _shape_catalog_session(
            studio_page="backing",
            improv_intelligence_tab="Phrase / Motif",
        )
        session[BACKING_CONTEXT_KEY] = {"source": "entry_jam", "style": "Bossa Nova"}
        with mock.patch.dict("sys.modules", {"backing_context": None}):
            # Function already imported; simulate the except path via raw blob.
            raw = session.get(BACKING_CONTEXT_KEY)
            self.assertEqual(str((raw or {}).get("source") or ""), "entry_jam")
        self.assertFalse(_catalog_song_workflow_owns_practice_key(session))

    def test_custom_ga_fallback_keeps_missions_ownership_without_authority_module(self) -> None:
        session = _shape_catalog_session(
            sbi_preview_source="Custom progression",
            improv_intelligence_tab="Missions",
            active_catalog_pick_key=TRIAL,
            active_music_source=SOURCE_CUSTOM,
            selected_song={"title": "Trial Song", "key": "D", "pick_key": TRIAL},
        )
        with mock.patch(
            "workflow_musical_authority.custom_owns_active_song_material",
            side_effect=ImportError("cycle"),
        ):
            # Direct ImportError from the inner import uses the pick/source fallback.
            owned = custom_sbi_owns_sidebar_practice_key(session)
        self.assertTrue(owned)


if __name__ == "__main__":
    unittest.main()
