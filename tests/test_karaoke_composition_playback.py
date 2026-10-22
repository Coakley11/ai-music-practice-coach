"""A Composition Now Singing entry plays from one canonical form, without touching Now Editing.

Generation, the player signature, the chart and the Lead Sheet read the same
ordered Composition form. Global ownership code (the sidebar Practice Key owner,
the source reconcile, the Now Editing defaults sync) leaves a Karaoke-bound
Backing take alone.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import karaoke_mode as km
from backing_context import (
    build_composition_song_context,
    get_backing_context,
    sections_dict_from_backing_context,
    set_backing_context,
)
from backing_practice_key_control import OWNER_CATALOG, resolve_backing_pk_control_owner
from backing_source_navigation import (
    bind_karaoke_performance_backing,
    karaoke_owns_backing_transport,
    karaoke_performance_owns_backing,
)
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_session_state import COMPOSER_LIBRARY_KEY, save_document_to_library
from composition_songs_bridge import composition_pick_key_for, composition_playback_sections
from music_source_ownership import reconcile_source_ownership
from music_theory import transpose_sections
from songs.key_state import resolve_display_key_widget_owner_id
from songs.music_source import (
    ACTIVE_MUSIC_SOURCE_KEY,
    EXPLICIT_MUSIC_SOURCE_CHOICE_KEY,
    SOURCE_CATALOG,
    _build_composition_chart_bundle,
)
from songs.playback_defaults import LAST_BACKING_DEFAULTS_SONG_ID, sync_playback_defaults_for_active_song
from songs.state import ACTIVE_CATALOG_PICK_KEY, SELECTED_SONG_STATE_KEY

SHALLOW = "Pop\x1fShallow — Lady Gaga"
RIVER_CHORDS = ["D", "Bm", "G", "A", "D", "Bm", "G", "A"]


def _river() -> dict:
    """River Comp: D major, 82 BPM, Verse / Chorus / Verse / Chorus with a repeated Verse."""
    doc = bootstrap_from_vision(genre="Pop", song_idea="River Comp", title="River Comp", key="D", bpm=82)
    apply_structure_template(doc, "simple")
    apply_section_chords(doc, str(ordered_sections(doc)[0]["id"]), parse_chord_paste("D Bm G A"))
    return doc


def _singing_river(**extra) -> tuple[dict, dict, str]:
    """Now Editing Shallow (G); Now Singing River Comp (D, 82)."""
    doc = _river()
    pick = composition_pick_key_for(doc)
    ss = {
        "instrument": "Voice",
        "studio_page": "backing",
        "karaoke_queue": [],
        COMPOSER_LIBRARY_KEY: {},
        "practice_key_by_source": {},
        "display_key": "G",
        "concert_key": "G",
        "backing_track_bpm": 96,
        "bpm": 96,
        ACTIVE_CATALOG_PICK_KEY: SHALLOW,
        ACTIVE_MUSIC_SOURCE_KEY: SOURCE_CATALOG,
        EXPLICIT_MUSIC_SOURCE_CHOICE_KEY: SOURCE_CATALOG,
        SELECTED_SONG_STATE_KEY: {"pick_key": SHALLOW, "title": "Shallow", "artist": "Lady Gaga", "key": "G"},
    }
    ss.update(extra)
    save_document_to_library(ss, doc)
    km.add_to_queue(ss, SHALLOW, title="Shallow", practice_key="G", bpm=96)
    km.add_to_queue(ss, pick, title="River Comp", artist="Composition", practice_key="D", bpm=82)
    km.start_session(ss, starting_pick_key=pick)
    return ss, doc, pick


def _flat(sections: dict) -> list[str]:
    return [c for row in sections.values() for c in row]


class TestCanonicalCompositionForm(unittest.TestCase):
    def test_playback_sections_keep_the_repeated_verse(self) -> None:
        sections = composition_playback_sections(_river(), "D")
        self.assertEqual(list(sections), ["Verse", "Verse 2"])
        self.assertEqual(_flat(sections), RIVER_CHORDS)

    def test_generation_context_and_chart_bundle_are_one_form(self) -> None:
        ss, doc, pick = _singing_river()
        chart = _build_composition_chart_bundle(
            ss, display_key="D", transpose_sections=transpose_sections, doc=doc
        )["sections"]
        ctx = build_composition_song_context(ss, doc=doc, write_global_keys=False)
        ctx.bound_pick_key = pick
        self.assertEqual(list(ctx.progression), _flat(chart))
        # Generation reads the same labels, order and chords as the chart and player.
        self.assertEqual(sections_dict_from_backing_context(ss, ctx), chart)

    def test_entry_key_transposes_the_whole_form(self) -> None:
        self.assertEqual(_flat(composition_playback_sections(_river(), "E")), ["E", "C#m", "A", "B"] * 2)


class TestNowEditingIsolation(unittest.TestCase):
    def test_binding_the_composition_entry_does_not_activate_it(self) -> None:
        ss, _doc, pick = _singing_river()
        ctx = bind_karaoke_performance_backing(ss)
        self.assertEqual(ctx.source, "composition_song")
        self.assertEqual(ctx.bound_pick_key, pick)
        self.assertEqual((ctx.concert_key, ctx.bpm), ("D", 82))
        self.assertEqual(ss[ACTIVE_CATALOG_PICK_KEY], SHALLOW)
        self.assertEqual(ss[ACTIVE_MUSIC_SOURCE_KEY], SOURCE_CATALOG)
        self.assertEqual((ss["display_key"], ss["concert_key"]), ("G", "G"))

    def test_sidebar_key_owner_stays_now_editing(self) -> None:
        ss, _doc, _pick = _singing_river()
        bind_karaoke_performance_backing(ss)
        self.assertTrue(karaoke_performance_owns_backing(ss))
        self.assertEqual(resolve_display_key_widget_owner_id(ss), f"catalog::{SHALLOW}")
        self.assertEqual(resolve_backing_pk_control_owner(ss), OWNER_CATALOG)

    def test_source_reconcile_leaves_the_karaoke_take(self) -> None:
        ss, _doc, pick = _singing_river()
        bind_karaoke_performance_backing(ss)
        ss["_last_backing_signature"] = ("River Comp", "D")
        ss["_last_backing_wav_path"] = "river.wav"
        self.assertFalse(reconcile_source_ownership(ss))
        self.assertEqual(get_backing_context(ss).bound_pick_key, pick)
        self.assertEqual(ss["_last_backing_wav_path"], "river.wav")
        self.assertEqual((ss["display_key"], ss[ACTIVE_CATALOG_PICK_KEY]), ("G", SHALLOW))

    def test_now_editing_defaults_sync_keeps_the_karaoke_take(self) -> None:
        ss, _doc, _pick = _singing_river()
        bind_karaoke_performance_backing(ss)
        ss["backing_track_bpm"] = 82
        ss["_last_backing_signature"] = ("River Comp", "D")
        ss["_last_backing_wav_path"] = "river.wav"
        # The Backing page last keyed the shared defaults id to Now Singing.
        ss[LAST_BACKING_DEFAULTS_SONG_ID] = "pk::river"
        bpm, _groove = sync_playback_defaults_for_active_song(
            SimpleNamespace(session_state=ss),
            song_id="Shallow",
            default_bpm=96,
            default_groove="Pop groove",
            pick_key=SHALLOW,
        )
        self.assertTrue(karaoke_owns_backing_transport(ss))
        self.assertEqual(bpm, 82)
        self.assertEqual(ss["_last_backing_wav_path"], "river.wav")
        self.assertEqual(ss["_last_backing_signature"], ("River Comp", "D"))

    def test_off_karaoke_the_context_owner_rule_is_unchanged(self) -> None:
        ss, doc, pick = _singing_river()
        km.stop_session(ss)
        ctx = build_composition_song_context(ss, doc=doc, write_global_keys=False)
        ctx.bound_pick_key = pick
        set_backing_context(ss, ctx)
        self.assertFalse(karaoke_performance_owns_backing(ss))
        self.assertFalse(karaoke_owns_backing_transport(ss))
        # Without a set, the Backing context still owns the widget as before.
        self.assertEqual(resolve_display_key_widget_owner_id(ss), f"composition::{pick}")


class TestGenerationInvariant(unittest.TestCase):
    SIG = ("River Comp", "D", "Intermediate", "Pop groove", 82)

    def test_missing_wav_without_matching_build_requires_generation_once(self) -> None:
        ss: dict = {}
        args = dict(has_chords=True, has_exact_wav=False, has_exact_build=False)
        self.assertTrue(km.karaoke_take_requires_generation(ss, self.SIG, **args))
        # A failed attempt for the same signature does not loop.
        self.assertFalse(km.karaoke_take_requires_generation(ss, self.SIG, **args))
        # A different destination signature is generated again.
        self.assertTrue(km.karaoke_take_requires_generation(ss, self.SIG[:4] + (95,), **args))

    def test_exact_wav_or_matching_build_needs_nothing(self) -> None:
        ss: dict = {}
        self.assertFalse(
            km.karaoke_take_requires_generation(ss, self.SIG, has_chords=True, has_exact_wav=True, has_exact_build=False)
        )
        self.assertFalse(
            km.karaoke_take_requires_generation(ss, self.SIG, has_chords=True, has_exact_wav=False, has_exact_build=True)
        )
        self.assertFalse(
            km.karaoke_take_requires_generation(ss, self.SIG, has_chords=False, has_exact_wav=False, has_exact_build=False)
        )

    def test_transition_clears_the_attempt_and_the_outgoing_build(self) -> None:
        from karaoke_ui import _invalidate_stale_backing_for_karaoke_transition

        ss = {
            km.KARAOKE_GENERATION_ATTEMPT_KEY: self.SIG,
            "_backing_wav_building_signature": ("Blues in F minor", "Fm"),
            "_last_backing_signature": ("Blues in F minor", "Fm"),
        }
        _invalidate_stale_backing_for_karaoke_transition(ss)
        self.assertNotIn(km.KARAOKE_GENERATION_ATTEMPT_KEY, ss)
        self.assertNotIn("_backing_wav_building_signature", ss)
        self.assertNotIn("_last_backing_signature", ss)


if __name__ == "__main__":
    unittest.main()
