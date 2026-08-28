"""Creative Backing Stabilization — Daniel QA regressions A–H on the Custom/Mission/Motif/Jam paths."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from app_ui import STUDIO_PAGE_META, nav_icon_button_label
from cpl_page_ui import custom_page_exit_nav_items
from custom_page_return_destination import (
    consume_custom_page_return_destination,
    peek_custom_page_return_destination,
    seal_custom_page_return_destination,
)
from custom_progression_lab import CPL_ACTIVE_KEY, apply_cpl_session_progression, prepare_cpl_backing_handoff
from custom_sbi_page_origin import (
    CUSTOM_SBI_PAGE_ORIGIN_KEY,
    consume_custom_sbi_page_origin_on_creative,
    stamp_custom_sbi_page_origin,
)
from improvisation_intelligence_ui import _motif_display_text
from improvisation_intelligence import ChordCoachInsight
from improvisation_motif import (
    _beats_of_rhythm_symbol,
    _rhythm_edit_distance,
    build_motif_abc,
    build_motif_pattern,
    format_motif_pattern_display,
    generate_motif_for_chord,
    motif_rhythm_symbols,
    parse_motif_abc_note_names,
    transform_motif,
    vary_motif_rhythm,
)
from improvisation_missions import MISSION_EXAMPLE_KEY, MissionExample
from mission_backing_alignment import build_mission_backing_alignment_payload
from mission_backing_transpose import (
    apply_mission_backing_practice_key_interval,
    mission_card_progression_symbols,
)
from mission_return_destination import (
    apply_sealed_mission_return_destination,
    build_mission_return_destination,
    peek_mission_return_destination,
    seal_mission_return_destination,
)
from music_theory import NOTE_TO_MIDI, normalize_root, split_chord
from songs.music_source import (
    CATALOG_BEFORE_CREATIVE_KEY,
    LAST_CUSTOM_STATE_KEY,
    SOURCE_CATALOG,
    restore_sbi_active_from_sealed_global_owner,
    snapshot_catalog_before_creative,
    snapshot_last_custom_state,
)
from source_session_state import get_sbi_preview_source, resolve_sbi_preview, set_sbi_preview_source


PK_SHAPE = "Pop\x1fShape of You"


def _trial_active() -> dict:
    return {
        "id": "trial-ah-1",
        "name": "Trial Song",
        "original_key_center": "D",
        "original_sections": {
            "Intro": [],
            "Verse": [
                {"chord": "Em", "bars": 1},
                {"chord": "Em", "bars": 1},
                {"chord": "D", "bars": 1},
                {"chord": "D", "bars": 1},
            ],
            "Pre-Chorus": [],
            "Chorus": [],
            "Bridge": [],
            "Solo": [],
            "Outro": [],
        },
        "bpm": 100,
        "progression_style": "Pop",
        "groove_style": "Pop",
    }


def _shape_session(*, practice_key: str = "Dm") -> dict:
    trial = _trial_active()
    return {
        "studio_page": "creative",
        "active_music_source": SOURCE_CATALOG,
        "active_catalog_pick_key": PK_SHAPE,
        "song": "Shape of You",
        "active_song_title": "Shape of You",
        "display_key": practice_key,
        "concert_key": practice_key,
        "selected_song": {
            "pick_key": PK_SHAPE,
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "key": "Bm",
        },
        "practice_key_by_source": {PK_SHAPE: practice_key},
        "catalog_session": {
            "pick_key": PK_SHAPE,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
            "display_key": practice_key,
            "original_key": "Bm",
        },
        CATALOG_BEFORE_CREATIVE_KEY: {
            "pick_key": PK_SHAPE,
            "original_key": "Bm",
            "display_key": practice_key,
            "selected_song": {
                "pick_key": PK_SHAPE,
                "title": "Shape of You",
                "artist": "Ed Sheeran",
                "key": "Bm",
            },
        },
        CPL_ACTIVE_KEY: copy.deepcopy(trial),
        LAST_CUSTOM_STATE_KEY: {
            "name": "Trial Song",
            "pick_key": "custom::trial-ah-1",
            "custom_home_key": "D",
            "active": copy.deepcopy(trial),
        },
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_intelligence_tab": "Entry & Jam",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
    }


def _pc(note: str) -> int:
    return NOTE_TO_MIDI.get(normalize_root(split_chord(str(note))[0]), 60) % 12


class TestACustomPageExitNav(unittest.TestCase):
    def test_finished_view_exposes_songs_and_practice_icon_exits(self) -> None:
        items = custom_page_exit_nav_items()
        self.assertEqual([i["destination"] for i in items], ["picker", "practice"])
        self.assertEqual(items[0]["label"], nav_icon_button_label("picker"))
        self.assertEqual(items[1]["label"], nav_icon_button_label("practice"))
        self.assertEqual(items[0]["icon"], STUDIO_PAGE_META["picker"]["icon"])
        self.assertEqual(items[1]["icon"], STUDIO_PAGE_META["practice"]["icon"])
        self.assertIn("Songs", items[0]["label"])
        self.assertIn("Practice", items[1]["label"])
        self.assertTrue(items[0]["icon"])
        self.assertTrue(items[1]["icon"])
        import cpl_page_ui
        import inspect

        src = inspect.getsource(cpl_page_ui)
        self.assertIn("custom_page_exit_nav_items()", src)
        self.assertIn('key=f"cpl_exit_{dest}_finish"', src)
        self.assertIn("_go_songs()", src)
        self.assertIn("_open_practice()", src)


class TestBCustomBackingReturn(unittest.TestCase):
    def test_custom_backing_return_restores_trial_workspace_without_seizing_ga(self) -> None:
        session = _shape_session()
        apply_cpl_session_progression(session, _trial_active(), reset_display_key=False)
        session["studio_page"] = "custom"
        session["cpl_finished"] = True
        session["cpl_edit_section"] = "Verse"
        snapshot_last_custom_state(session)
        dest = seal_custom_page_return_destination(session)
        self.assertIsInstance(dest, dict)
        self.assertEqual(dest.get("destination_page"), "custom")
        self.assertEqual(dest.get("song_title"), "Trial Song")
        self.assertEqual(str((dest.get("active") or {}).get("name") or ""), "Trial Song")
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)

        session["studio_page"] = "backing"
        session[CPL_ACTIVE_KEY] = {"name": "My Progression", "original_sections": {}}
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["sbi_preview_source"] = "Active song"
        ok = consume_custom_page_return_destination(session)
        self.assertTrue(ok)
        self.assertEqual(session.get("studio_page"), "custom")
        self.assertEqual(str((session.get(CPL_ACTIVE_KEY) or {}).get("name") or ""), "Trial Song")
        verse = (session.get(CPL_ACTIVE_KEY) or {}).get("original_sections", {}).get("Verse") or []
        self.assertGreaterEqual(len(verse), 4)
        self.assertEqual(session.get("active_music_source"), SOURCE_CATALOG)
        self.assertEqual(session.get("active_catalog_pick_key"), PK_SHAPE)
        self.assertEqual(session.get("song"), "Shape of You")


class TestCCustomSbiPageOrigin(unittest.TestCase):
    def test_custom_sbi_custom_page_creative_restores_trial_not_active_sbi(self) -> None:
        session = _shape_session()
        apply_cpl_session_progression(session, _trial_active(), reset_display_key=False)
        snapshot_last_custom_state(session)
        set_sbi_preview_source(session, "Custom progression")
        session["improv_song_source"] = "Custom progression"
        ga_before = {
            "source": session.get("active_music_source"),
            "pick": session.get("active_catalog_pick_key"),
            "title": session.get("song"),
        }

        origin = stamp_custom_sbi_page_origin(session)
        self.assertIsInstance(origin, dict)
        self.assertEqual(origin.get("source"), "Custom progression")
        self.assertEqual(origin.get("song_title"), "Trial Song")
        session["studio_page"] = "custom"
        session["improv_song_source"] = "Active song"
        session["sbi_preview_source"] = "Active song"

        session["studio_page"] = "creative"
        from creative_session_state import hydrate_creative_session_for_page

        with patch("songs.state.persist_music_local_state"), patch(
            "songs.music_source.persist_music_local_state", create=True
        ):
            hydrate_creative_session_for_page(session)
        if session.get(CUSTOM_SBI_PAGE_ORIGIN_KEY):
            consume_custom_sbi_page_origin_on_creative(session)

        self.assertEqual(get_sbi_preview_source(session), "Custom progression")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("title"), "Trial Song")
        self.assertEqual(preview.get("source"), "Custom progression")
        chords = [c for chs in (preview.get("sections") or {}).values() for c in chs]
        self.assertIn("Em", chords)
        self.assertIn("D", chords)
        self.assertEqual(session.get("active_music_source"), ga_before["source"])
        self.assertEqual(session.get("active_catalog_pick_key"), ga_before["pick"])
        self.assertEqual(session.get("song"), ga_before["title"])


class TestDEMissionBackingInterval(unittest.TestCase):
    def _seal_gm_example(self, session: dict) -> dict:
        example = MissionExample(
            mission="Outline chord tones",
            variant="normal",
            chord="Gm",
            section="Chorus",
            song_title="Shape of You",
            display_key="Dm",
            concert_key="Dm",
            instrument="Piano",
            level="Intermediate",
            focus="Improvisation",
            motif={
                "chord": "Gm",
                "notes": ["Bb", "D", "G"],
                "midi": [70, 74, 79],
                "display": "Bb – D – G",
                "rhythm": "♩ ♩ ♩",
                "rhythm_symbols": ["♩", "♩", "♩"],
            },
            abc="",
            tab="",
            piano_html="",
            why="",
            practice_steps=[],
            insight=ChordCoachInsight(
                chord="Gm",
                scales=[],
                scale_suggestions=[],
                chord_tones=["Bb", "D", "G"],
                tensions=[],
                avoid_notes=[],
                target_notes=[],
                motif_idea="",
                resolve_hint="",
            ),
            show_tab=False,
            show_piano=False,
        )
        align = build_mission_backing_alignment_payload(
            session,
            mission="Outline chord tones",
            cur_chord="Gm",
            section_label="Chorus",
            chord_idx=1,
            song_title="Shape of You",
            song_pick_key=PK_SHAPE,
            concert_key="Dm",
            display_key="Dm",
            example=example,
        )
        dest = build_mission_return_destination(
            align, handoff_mode="mission_backing", with_practice_lick=False, request_seq=1
        )
        seal_mission_return_destination(session, dest)
        session["ii_selected_chord"] = "Gm"
        session["II_SELECTED_CHORD"] = "Gm"
        session["ii_selected_section"] = "Chorus"
        session[MISSION_EXAMPLE_KEY] = {
            "chord": "Gm",
            "mission": "Outline chord tones",
            "section": "Chorus",
            "concert_key": "Dm",
            "display_key": "Dm",
            "motif": dict(example.motif),
            "abc": "",
        }
        return dest

    def test_one_semitone_up_projects_gm_and_bb_once(self) -> None:
        session = _shape_session(practice_key="Dm")
        session["studio_page"] = "backing"
        self._seal_gm_example(session)
        dest = apply_mission_backing_practice_key_interval(session, "D#m", from_key="Dm")
        self.assertIsInstance(dest, dict)
        chord = str(dest.get("chord_symbol") or "")
        self.assertIn(_pc(chord), {_pc("G#m"), _pc("Abm")})
        notes = list(dest.get("example_notes") or [])
        self.assertTrue(notes)
        self.assertEqual(_pc(notes[0]), _pc("B"))
        card = mission_card_progression_symbols(session)
        self.assertTrue(card)
        self.assertIn(_pc(card[0]), {_pc("G#m"), _pc("Abm")})
        self.assertEqual(_pc(session.get("ii_selected_chord") or ""), _pc(chord))
        self.assertNotEqual(_pc(chord), _pc("A#m"))
        self.assertNotEqual(_pc(notes[0]), _pc("C#"))
        live_ex = session.get(MISSION_EXAMPLE_KEY) or {}
        live_notes = list((live_ex.get("motif") or {}).get("notes") or [])
        self.assertEqual(_pc(live_notes[0]), _pc("B"))

    def test_return_keeps_transposed_chord_and_example_not_song_tonic(self) -> None:
        session = _shape_session(practice_key="Dm")
        session["studio_page"] = "backing"
        self._seal_gm_example(session)
        apply_mission_backing_practice_key_interval(session, "Ebm", from_key="Dm")
        # Poison the live selection the way the song-tonic leak used to.
        session["ii_selected_chord"] = "D#m"
        session["II_SELECTED_CHORD"] = "D#m"
        dest = peek_mission_return_destination(session)
        self.assertIsInstance(dest, dict)
        self.assertNotEqual(_pc(str(dest.get("chord_symbol") or "")), _pc("D#m"))
        session["studio_page"] = "creative"
        self.assertTrue(apply_sealed_mission_return_destination(session, dest))
        returned = str(session.get("ii_selected_chord") or "")
        self.assertIn(_pc(returned), {_pc("G#m"), _pc("Abm")})
        self.assertNotEqual(_pc(returned), _pc("D#m"))
        raw = session.get(MISSION_EXAMPLE_KEY) or {}
        notes = list((raw.get("motif") or {}).get("notes") or [])
        self.assertTrue(notes)
        self.assertEqual(_pc(notes[0]), _pc("B"))
        self.assertEqual(str(raw.get("chord") or returned), returned)
        # Rerun/refresh must not replace the Mission chord with the song tonic.
        session["display_key"] = "Ebm"
        apply_sealed_mission_return_destination(session)
        self.assertIn(_pc(str(session.get("ii_selected_chord") or "")), {_pc("G#m"), _pc("Abm")})
        notes2 = list(((session.get(MISSION_EXAMPLE_KEY) or {}).get("motif") or {}).get("notes") or [])
        self.assertEqual(_pc(notes2[0]), _pc("B"))


class TestFGMotifRhythmAndCells(unittest.TestCase):
    def test_change_rhythm_is_bounded_variation(self) -> None:
        motif = generate_motif_for_chord("Am", key_center="A minor", level="Intermediate")
        before = motif_rhythm_symbols(motif)
        total = sum(_beats_of_rhythm_symbol(s) for s in before)
        changed = vary_motif_rhythm(motif, nonce=0)
        after = motif_rhythm_symbols(changed)
        self.assertEqual(list(changed.get("notes") or []), list(motif.get("notes") or []))
        self.assertEqual(sum(_beats_of_rhythm_symbol(s) for s in after), total)
        self.assertGreaterEqual(_rhythm_edit_distance(before, after), 1)
        self.assertLessEqual(_rhythm_edit_distance(before, after), max(2, max(1, len(before) // 2)))
        again = vary_motif_rhythm(motif, nonce=0)
        self.assertEqual(motif_rhythm_symbols(again), after)
        abc = build_motif_abc(changed, key_center="A minor", bpm=100)
        parsed = parse_motif_abc_note_names(abc)
        self.assertEqual([_pc(n) for n in parsed], [_pc(n) for n in (changed.get("notes") or [])])

    def test_transform_change_rhythm_does_not_cycle_catalog(self) -> None:
        motif = generate_motif_for_chord("Em", key_center="E minor", level="Intermediate")
        out = transform_motif(motif, "change_rhythm", key_center="E minor")
        self.assertEqual(list(out.get("notes") or []), list(motif.get("notes") or []))
        self.assertTrue(str(out.get("rhythm_key") or "").startswith("varied-"))

    def test_pattern_display_uses_actual_cell_boundaries(self) -> None:
        motif = generate_motif_for_chord("Ab", key_center="Ab", level="Intermediate")
        pattern = build_motif_pattern(
            motif,
            key_center="Ab",
            pattern_type="diatonic",
            direction="descending",
            length=8,
        )
        cells = list(pattern.get("cells") or [])
        self.assertGreaterEqual(len(cells), 2)
        rendered = _motif_display_text(pattern)
        expected = format_motif_pattern_display(cells)
        self.assertEqual(rendered, expected)
        self.assertIn(" | ", rendered)
        parts = [p.strip() for p in rendered.split("|")]
        self.assertEqual(len(parts), len(cells))
        for part, cell in zip(parts, cells):
            self.assertEqual([n.strip() for n in part.split("–")], list(cell))


class TestHEntryJamRestoresSbiActive(unittest.TestCase):
    def test_entry_jam_return_then_sbi_active_is_shape_not_trial(self) -> None:
        session = _shape_session(practice_key="D#m")
        apply_cpl_session_progression(session, _trial_active(), reset_display_key=False)
        snapshot_last_custom_state(session)
        set_sbi_preview_source(session, "Custom progression")
        session["improv_song_source"] = "Custom progression"
        snapshot_catalog_before_creative(session, refresh_if_pick_changed=True)
        from songs.practice_key_state import set_practice_concert_key

        set_practice_concert_key(session, "D#m", pick_key=PK_SHAPE)

        from backing_creative_return_route import apply_creative_return_route

        apply_creative_return_route(
            session,
            {
                "intelligence_tab": "Entry & Jam",
                "entry_mode": "Style Jam Mode",
                "workflow_owner": "style_jam",
                "backing_source": "entry_jam",
            },
        )
        restore_sbi_active_from_sealed_global_owner(session)
        session["improv_entry_mode"] = "Song-Based Improvisation"
        session["improv_intelligence_tab"] = "Entry & Jam"

        self.assertEqual(get_sbi_preview_source(session), "Active song")
        preview = resolve_sbi_preview(session)
        self.assertEqual(preview.get("title"), "Shape of You")
        self.assertEqual(session.get("active_catalog_pick_key"), PK_SHAPE)
        from songs.practice_key_state import get_practice_concert_key

        self.assertIn(_pc(get_practice_concert_key(session, PK_SHAPE) or ""), {_pc("D#m"), _pc("Ebm")})
        last = session.get(LAST_CUSTOM_STATE_KEY) or {}
        self.assertEqual(str((last.get("active") or {}).get("name") or last.get("name") or ""), "Trial Song")
        set_sbi_preview_source(session, "Custom progression")
        custom_preview = resolve_sbi_preview(session)
        self.assertEqual(custom_preview.get("title"), "Trial Song")


if __name__ == "__main__":
    unittest.main()
