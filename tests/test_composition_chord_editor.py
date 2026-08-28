"""Manual / advanced chord editor — widget ownership, edits, restore."""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from composition_chord_editor import (
    apply_draft_to_document,
    cancel_editor_draft,
    chromatic_warning,
    consume_refine_intent_choice,
    draft_changed,
    insert_draft_chord,
    is_chromatic_to_key,
    legacy_refine_intent_key,
    location_labels,
    parse_chord_parts,
    prepare_editor_widgets,
    prepare_refine_intent_widget,
    push_editor_history,
    quality_choices,
    queue_editor_draft,
    queue_refine_intent_change,
    refine_intent_pending_key,
    refine_intent_value_key,
    refine_intent_widget_key,
    replace_draft_chord,
    seed_editor_draft,
    strip_edit_metadata,
    suggest_slot_chords,
    undo_editor_draft,
    build_chord_symbol,
)
from composition_chord_refinements import CHORD_REFINEMENT_INTENTS
from composition_document import (
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    chords_for_playback,
    insert_section_chord,
    ordered_sections,
    parse_chord_paste,
    set_workflow_phase,
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_ACTIVE_SECTION_KEY,
    COMPOSER_FOCUS_LANE_KEY,
    COMPOSER_LIBRARY_KEY,
    set_active_document,
)
from composition_studio_page import (
    _render_chord_refinement_panel,
    _render_manual_chord_editor,
    _render_phase_chords,
)
from composition_workspace_state_persistence import (
    apply_composition_workspace_from_payload,
    gather_composition_workspace_from_session,
    prepare_composition_workspace_for_render,
    sync_composition_workspace_before_persist,
)
from music_persistent_state import apply_music_disk_state, build_music_disk_state


class _WidgetLockedSession(dict):
    """Stand-in for Streamlit session_state after named widgets exist."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked: set[str] = set()

    def lock(self, *keys: str) -> None:
        self.locked.update(keys)

    def __setitem__(self, key, value):  # type: ignore[override]
        if key in self.locked:
            raise RuntimeError(
                f"StreamlitAPIException: `{key}` cannot be modified after the widget is instantiated"
            )
        super().__setitem__(key, value)


def _song():
    doc = bootstrap_from_vision(
        genre="Pop",
        song_idea="Editor tests",
        title="Editor Song",
        key="C major",
        bpm=100,
        meter="4/4",
    )
    apply_structure_template(doc, "simple")
    verse, chorus = ordered_sections(doc)[0], ordered_sections(doc)[1]
    apply_section_chords(doc, str(verse["id"]), parse_chord_paste("C Am F G"))
    apply_section_chords(doc, str(chorus["id"]), parse_chord_paste("F G C C"))
    set_workflow_phase(doc, "chords")
    return doc, verse, chorus


class TestRefineIntentWidgetOwnership(unittest.TestCase):
    def test_try_another_does_not_write_live_widget_key(self) -> None:
        ids = [i[0] for i in CHORD_REFINEMENT_INTENTS]
        sid = "sec-a"
        ss = _WidgetLockedSession()
        prepare_refine_intent_widget(ss, sid, ids)
        widget_k = refine_intent_widget_key(sid)
        self.assertEqual(ss[widget_k], ids[0])
        ss.lock(widget_k, legacy_refine_intent_key(sid))
        consume_refine_intent_choice(ss, sid, ids[0])
        nxt = ids[1]
        queue_refine_intent_change(ss, sid, nxt)
        self.assertEqual(ss[widget_k], ids[0])
        self.assertEqual(ss[refine_intent_pending_key(sid)], nxt)
        self.assertEqual(ss[refine_intent_value_key(sid)], nxt)
        ss.locked.clear()
        prepared = prepare_refine_intent_widget(ss, sid, ids)
        self.assertEqual(prepared, nxt)
        self.assertEqual(ss[widget_k], nxt)
        self.assertNotIn(refine_intent_pending_key(sid), ss)

    def test_section_intents_do_not_leak(self) -> None:
        ids = [i[0] for i in CHORD_REFINEMENT_INTENTS]
        ss: dict = {}
        prepare_refine_intent_widget(ss, "verse", ids)
        queue_refine_intent_change(ss, "verse", "darker")
        prepare_refine_intent_widget(ss, "verse", ids)
        prepare_refine_intent_widget(ss, "chorus", ids)
        self.assertEqual(ss[refine_intent_widget_key("verse")], "darker")
        self.assertEqual(ss[refine_intent_widget_key("chorus")], ids[0])

    def test_render_source_never_assigns_legacy_widget_key(self) -> None:
        src = inspect.getsource(_render_chord_refinement_panel)
        self.assertIn("queue_refine_intent_change", src)
        self.assertIn("prepare_refine_intent_widget", src)
        self.assertIn("refine_intent_widget_key", src)
        self.assertNotIn('session_state[f"composer_refine_intent_{section_id}"]', src)
        self.assertNotIn("composer_refine_intent_{section_id}", src)
        page = inspect.getsource(_render_phase_chords)
        self.assertIn("Manual / advanced chord editor", page)
        self.assertIn("_render_manual_chord_editor", page)
        editor = inspect.getsource(_render_manual_chord_editor)
        self.assertIn("Accept edit", editor)
        self.assertIn("apply_draft_to_document", editor)
        self.assertIn("does not open the Custom Progression page", editor)
        self.assertNotIn("studio_page", editor)


class TestManualEditorLogic(unittest.TestCase):
    def test_location_labels_use_bar_and_duration(self) -> None:
        entries = [
            {"chord": "C", "bars": 1},
            {"chord": "Am", "duration_beats": 2.0},
            {"chord": "F", "duration_beats": 2.0},
            {"chord": "G", "bars": 2},
        ]
        labels = location_labels(entries, meter="4/4")
        self.assertEqual(len(labels), 4)
        self.assertIn("Bar 1", labels[0])
        self.assertIn("1 bar", labels[0])
        self.assertIn("Bar 2", labels[1])
        self.assertIn("2 beats", labels[1])
        self.assertIn("Bar 2", labels[2])
        self.assertIn("2 bars", labels[3])

    def test_parse_and_build_qualities(self) -> None:
        cases = {
            "C": ("C", ""),
            "Am": ("A", "m"),
            "G7": ("G", "7"),
            "Fmaj7": ("F", "maj7"),
            "Dm7": ("D", "m7"),
            "Gsus4": ("G", "sus4"),
            "Cadd9": ("C", "add9"),
            "Bdim": ("B", "dim"),
            "Bm7b5": ("B", "m7b5"),
            "Caug": ("C", "aug"),
            "D7b5": ("D", "7b5"),
            "E7#5": ("E", "7#5"),
            "G/B": ("G", ""),
        }
        for sym, (root, qual) in cases.items():
            parts = parse_chord_parts(sym)
            self.assertEqual(parts["root"], root, sym)
            self.assertEqual(parts["quality"], qual, sym)
        self.assertEqual(build_chord_symbol("C", "maj7"), "Cmaj7")
        self.assertIn("m7b5", quality_choices("m7b5"))

    def test_replace_insert_preview_accept_isolates_section(self) -> None:
        doc, verse, chorus = _song()
        ss: dict = {}
        draft = seed_editor_draft(ss, str(verse["id"]), verse["chords"])
        push_editor_history(ss, str(verse["id"]), draft)
        draft = replace_draft_chord(draft, 1, "Am7")
        self.assertEqual(strip_edit_metadata(draft)[1]["chord"], "Am7")
        self.assertEqual(verse["chords"][1]["chord"], "Am")
        push_editor_history(ss, str(verse["id"]), draft)
        draft = insert_draft_chord(draft, len(draft), "G7", duration="2beat")
        self.assertEqual(draft[-1]["chord"], "G7")
        self.assertEqual(draft[-1].get("duration_beats"), 2.0)
        chorus_before = [c["chord"] for c in chorus["chords"]]
        self.assertTrue(apply_draft_to_document(doc, str(verse["id"]), draft))
        self.assertEqual(verse["chords"][1]["chord"], "Am7")
        self.assertEqual(verse["chords"][-1]["chord"], "G7")
        self.assertEqual(verse["chords"][-1].get("duration_beats"), 2.0)
        self.assertEqual([c["chord"] for c in chorus["chords"]], chorus_before)

    def test_undo_and_cancel_restore_draft_not_document(self) -> None:
        doc, verse, _chorus = _song()
        sid = str(verse["id"])
        ss: dict = {}
        original = [c["chord"] for c in verse["chords"]]
        draft = seed_editor_draft(ss, sid, verse["chords"])
        push_editor_history(ss, sid, draft)
        changed = replace_draft_chord(draft, 0, "Cmaj7")
        queue_editor_draft(ss, sid, changed)
        draft = prepare_editor_widgets(ss, sid, verse["chords"])
        self.assertEqual(draft[0]["chord"], "Cmaj7")
        undo_editor_draft(ss, sid)
        draft = prepare_editor_widgets(ss, sid, verse["chords"])
        self.assertEqual(draft[0]["chord"], "C")
        push_editor_history(ss, sid, draft)
        queue_editor_draft(ss, sid, replace_draft_chord(draft, 2, "Fmaj7"))
        cancel_editor_draft(ss, sid)
        draft = prepare_editor_widgets(ss, sid, verse["chords"])
        self.assertEqual([c["chord"] for c in strip_edit_metadata(draft)], original)
        self.assertEqual([c["chord"] for c in verse["chords"]], original)
        self.assertTrue(draft_changed(replace_draft_chord(draft, 0, "C7"), verse["chords"]))

    def test_suggestions_are_key_aware_and_warn_chromatic(self) -> None:
        doc, verse, _ = _song()
        ideas = suggest_slot_chords(doc, verse, list(verse["chords"]), 1, limit=3)
        self.assertGreaterEqual(len(ideas), 1)
        self.assertTrue(all(i.get("symbol") for i in ideas))
        self.assertFalse(is_chromatic_to_key("F", "C"))
        self.assertTrue(is_chromatic_to_key("Ab", "C"))
        warn = chromatic_warning("Ab", "C")
        self.assertIn("outside", warn.lower())
        self.assertIn("color", warn.lower())
        self.assertFalse(chromatic_warning("F", "C"))

    def test_insert_section_chord_keeps_duration(self) -> None:
        doc, verse, _ = _song()
        self.assertTrue(
            insert_section_chord(doc, str(verse["id"]), 2, "Dm7", duration_beats=2.0)
        )
        self.assertEqual(verse["chords"][2]["chord"], "Dm7")
        self.assertEqual(verse["chords"][2]["duration_beats"], 2.0)

    def test_linked_repeat_updates_from_source_only(self) -> None:
        doc, verse, _chorus = _song()
        verse2 = next(s for s in ordered_sections(doc) if s.get("label_variant") == "Verse 2")
        link = verse2.setdefault("chord_link", {})
        link["linked"] = True
        link["source_section_id"] = str(verse["id"])
        ss: dict = {}
        draft = seed_editor_draft(ss, str(verse["id"]), verse["chords"])
        draft = replace_draft_chord(draft, 3, "G7")
        apply_draft_to_document(doc, str(verse["id"]), draft)
        self.assertEqual(verse["chords"][3]["chord"], "G7")
        self.assertEqual(verse2["chords"][3]["chord"], "G7")
        chorus = next(s for s in ordered_sections(doc) if "Chorus" in str(s.get("label_variant") or ""))
        self.assertEqual(chorus["chords"][0]["chord"], "F")

    def test_accept_survives_refresh_and_cold_restore(self) -> None:
        doc, verse, chorus = _song()
        ss = {
            "studio_page": "composer",
            COMPOSER_ACTIVE_KEY: doc,
            COMPOSER_LIBRARY_KEY: {str(doc["id"]): doc},
            COMPOSER_ACTIVE_SECTION_KEY: str(verse["id"]),
            COMPOSER_FOCUS_LANE_KEY: "chords",
        }
        draft = replace_draft_chord(list(verse["chords"]), 0, "Cmaj7")
        apply_draft_to_document(doc, str(verse["id"]), draft)
        set_active_document(ss, doc)
        sync_composition_workspace_before_persist(ss, reason="composer_edit")
        blob = gather_composition_workspace_from_session(ss)
        fresh: dict = {"studio_page": "composer"}
        apply_composition_workspace_from_payload(
            fresh, {"composition_workspace_state": blob}, authoritative=True
        )
        prepare_composition_workspace_for_render(fresh)
        restored = fresh[COMPOSER_ACTIVE_KEY]
        rverse = next(s for s in ordered_sections(restored) if s["id"] == verse["id"])
        rchorus = next(s for s in ordered_sections(restored) if s["id"] == chorus["id"])
        self.assertEqual(rverse["chords"][0]["chord"], "Cmaj7")
        self.assertEqual(rchorus["chords"][0]["chord"], "F")
        self.assertEqual(
            chords_for_playback(restored, scope="section", section_id=str(verse["id"]))[0],
            "Cmaj7",
        )

        class _St:
            def __init__(self, state):
                self.session_state = state

        disk = build_music_disk_state(_St(ss))
        cold: dict = {}
        apply_music_disk_state(
            _St(cold),
            disk,
            song_picker_catalog={},
            song_library={},
            authoritative_restore=True,
        )
        prepare_composition_workspace_for_render(cold)
        cold_doc = cold[COMPOSER_ACTIVE_KEY]
        self.assertEqual(ordered_sections(cold_doc)[0]["chords"][0]["chord"], "Cmaj7")


@unittest.skipUnless(
    __import__("importlib").util.find_spec("streamlit.testing.v1") is not None,
    "streamlit.testing.v1 unavailable",
)
class TestManualEditorAppTest(unittest.TestCase):
    HARNESS = str(Path(__file__).resolve().parents[1] / "composition_chord_editor_harness.py")

    def _run(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        return at

    def test_open_editor_change_refine_rerun_switch_restore(self) -> None:
        at = self._run()
        verse_id = str(at.session_state["harness_verse_id"])
        chorus_id = str(at.session_state["harness_chorus_id"])
        widget_k = refine_intent_widget_key(verse_id)
        self.assertIn(widget_k, at.session_state)

        expanders = [e for e in at.expander if "Manual / advanced" in str(getattr(e, "label", "") or "")]
        if expanders:
            try:
                expanders[0].expanded = True
                at.run(timeout=120)
            except Exception:
                pass
        self.assertFalse(at.exception, msg=repr(at.exception))

        box = at.selectbox(key=widget_k)
        box.set_value("darker").run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        value_k = refine_intent_value_key(verse_id)
        self.assertIn(value_k, at.session_state)
        self.assertEqual(str(at.session_state[value_k]), "darker")

        propose = [b for b in at.button if str(b.label) == "Propose change"]
        self.assertTrue(propose, [b.label for b in at.button])
        propose[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))

        another = [b for b in at.button if str(b.label) == "Try another"]
        self.assertTrue(another, [b.label for b in at.button])
        another[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertNotIn(legacy_refine_intent_key(verse_id), at.session_state)

        qual_key = f"composer_cedit_qual_{verse_id}_1"
        try:
            at.selectbox(key=qual_key).set_value("m7").run(timeout=120)
        except KeyError:
            self.fail(f"quality selectbox {qual_key} missing")
        self.assertFalse(at.exception, msg=repr(at.exception))

        accept = [b for b in at.button if str(b.label) == "Accept edit"]
        self.assertTrue(accept, [b.label for b in at.button])
        accept[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        doc = at.session_state[COMPOSER_ACTIVE_KEY]
        verse = next(s for s in ordered_sections(doc) if str(s["id"]) == verse_id)
        chorus = next(s for s in ordered_sections(doc) if str(s["id"]) == chorus_id)
        self.assertEqual(verse["chords"][1]["chord"], "Am7")
        self.assertEqual([c["chord"] for c in chorus["chords"]][:2], ["F", "G"])

        chorus_btn = [b for b in at.button if str(b.label) == "Chorus"]
        self.assertTrue(chorus_btn, [b.label for b in at.button])
        chorus_btn[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        self.assertIn(COMPOSER_ACTIVE_SECTION_KEY, at.session_state)
        self.assertEqual(str(at.session_state[COMPOSER_ACTIVE_SECTION_KEY]), chorus_id)
        chorus_widget = refine_intent_widget_key(chorus_id)
        verse_value_k = refine_intent_value_key(verse_id)
        chorus_value_k = refine_intent_value_key(chorus_id)
        if chorus_widget in at.session_state and verse_value_k in at.session_state:
            verse_intent = at.session_state[verse_value_k]
            chorus_intent = at.session_state[chorus_value_k] if chorus_value_k in at.session_state else None
            if chorus_intent:
                self.assertNotEqual(chorus_intent, verse_intent)

        refresh = [b for b in at.button if str(b.label) == "Harness: simulate refresh"]
        self.assertTrue(refresh)
        refresh[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        doc = at.session_state[COMPOSER_ACTIVE_KEY]
        verse = next(s for s in ordered_sections(doc) if str(s["id"]) == verse_id)
        self.assertEqual(verse["chords"][1]["chord"], "Am7")

        cold = [b for b in at.button if str(b.label) == "Harness: cold restore"]
        self.assertTrue(cold)
        cold[0].click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        doc = at.session_state[COMPOSER_ACTIVE_KEY]
        verse = next(s for s in ordered_sections(doc) if str(s["id"]) == verse_id)
        chorus = next(s for s in ordered_sections(doc) if str(s["id"]) == chorus_id)
        self.assertEqual(verse["chords"][1]["chord"], "Am7")
        self.assertEqual(chorus["chords"][0]["chord"], "F")


if __name__ == "__main__":
    unittest.main()
