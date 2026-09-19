"""Songs → Composition Studio Edit: selected library UUID must win."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from composition_document import (
    add_melody_phrase,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    get_workflow_phase,
    ordered_sections,
    parse_chord_paste,
    playback_globals,
    section_has_melody,
    set_workflow_phase,
)
from composition_session_state import (
    COMPOSER_ACTIVE_KEY,
    COMPOSER_LIBRARY_KEY,
    get_active_document,
    list_library_documents,
    save_document_to_library,
    set_active_document,
)
from composition_songs_bridge import (
    PENDING_COMPOSER_STUDIO_EDIT_ID_KEY,
    apply_pending_composer_studio_edit,
    composition_home_key,
    composition_id_from_pick_key,
    composition_pick_key_for,
    composition_selected_song_record,
    open_saved_composition_for_studio_edit,
    resolve_songs_composition_edit_id,
)
from studio_page_persistence import handle_studio_page_transition, save_page_snapshot


def _st(ss: dict) -> MagicMock:
    st = MagicMock()
    st.session_state = ss
    return st


def _tonic_from_key_label(key: str) -> str:
    raw = str(key or "C").strip()
    token = raw.split()[0] if raw else "C"
    if "minor" in raw.lower() and not token.lower().endswith("m"):
        return f"{token}m"
    return token


def _seed_doc(
    *,
    title: str,
    key: str,
    bpm: int,
    genre: str,
    idea: str,
    meter: str = "4/4",
    chords: str = "C G Am F",
    template: str = "simple",
    partial: bool = False,
) -> dict:
    doc = bootstrap_from_vision(
        genre=genre,
        song_idea=idea,
        title=title,
        mood="focused",
        energy="medium",
    )
    g = doc.setdefault("global", {})
    g["original_key_center"] = _tonic_from_key_label(key)
    g["bpm"] = int(bpm)
    g["time_signature"] = meter
    apply_structure_template(doc, template)
    secs = ordered_sections(doc)
    verse = secs[0]
    sid = str(verse["id"])
    entries = parse_chord_paste(chords)
    if len(entries) > 1:
        extra = dict(entries[-1])
        extra["chord"] = "Dm"
        entries.append(extra)
    apply_section_chords(doc, sid, entries)
    add_melody_phrase(doc, sid, label="Hook", motif="C4 E4 G4 A4", notes="C4 E4 G4 A4")
    verse = ordered_sections(doc)[0]
    if not partial:
        verse.setdefault("lyrics", {})["raw_text"] = "A line for the verse"
        verse["lyrics"]["lines"] = [{"text": "A line for the verse"}]
        doc["review"] = {"notes": "Keep the hook", "status": "sketched"}
        set_workflow_phase(doc, "review")
        doc["status"] = "draft"
    else:
        verse.setdefault("lyrics", {})["raw_text"] = ""
        verse["lyrics"]["lines"] = []
        doc.pop("review", None)
        set_workflow_phase(doc, "lyrics")
        doc["status"] = "draft"
    return doc


def _library_session(*docs: dict) -> dict:
    ss: dict = {
        "studio_page": "picker",
        "_studio_active_page_id": "picker",
        "instrument": "Piano",
        COMPOSER_LIBRARY_KEY: {},
        "composer_saved_compositions": {},
    }
    for doc in docs:
        set_active_document(ss, doc)
        save_document_to_library(ss, doc)
    return ss


def _open_edit(ss: dict, doc_id_or_pick: str) -> bool:
    with patch("studio_nav_history.navigate_studio_page") as nav:
        def _nav(session, page_id):
            session["studio_page"] = page_id
            return True

        nav.side_effect = _nav
        return open_saved_composition_for_studio_edit(_st(ss), doc_id_or_pick)


def _songs_to_studio_restore(ss: dict) -> None:
    """Reproduce picker → composer snapshot restore, then consume Edit handoff."""
    ss["_studio_active_page_id"] = "picker"
    ss["studio_page"] = "composer"
    handle_studio_page_transition(ss)
    apply_pending_composer_studio_edit(ss)


class TestSongsCompositionStudioEdit(unittest.TestCase):
    def setUp(self) -> None:
        self._save_patch = patch(
            "music_persistent_state.force_save_music_state",
            lambda *args, **kwargs: None,
        )
        self._save_patch.start()
        self.addCleanup(self._save_patch.stop)

    def test_songs_card_resolves_exact_uuid(self) -> None:
        doc = _seed_doc(
            title="Edit Test A",
            key="C major",
            bpm=100,
            genre="Pop",
            idea="Card identity",
        )
        card = composition_selected_song_record(doc)
        sid = str(doc["id"])
        self.assertEqual(card["pick_key"], f"composition::{sid}")
        self.assertEqual(composition_id_from_pick_key(card["pick_key"]), sid)
        self.assertEqual(card["title"], "Edit Test A")
        self.assertEqual(composition_pick_key_for(doc), f"composition::{sid}")

    def test_direct_edit_opens_selected_document(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="Song A")
        b = _seed_doc(title="Edit Test B", key="G major", bpm=120, genre="Rock", idea="Song B")
        ss = _library_session(a, b)
        set_active_document(ss, b)
        save_page_snapshot(ss, "composer")
        opened = _open_edit(ss, composition_pick_key_for(a))
        self.assertTrue(opened)
        self.assertEqual(ss.get(PENDING_COMPOSER_STUDIO_EDIT_ID_KEY), str(a["id"]))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), str(a["id"]))
        self.assertEqual(str(active.get("title")), "Edit Test A")
        self.assertEqual(ss.get("studio_page"), "composer")

    def test_active_composition_id_equals_selected_uuid(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="Song A")
        ss = _library_session(a)
        _open_edit(ss, str(a["id"]))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), str(a["id"]))
        self.assertNotEqual(str(active.get("id")), "")

    def test_a_then_b_opens_separate_documents(self) -> None:
        a = _seed_doc(
            title="Edit Test A",
            key="C major",
            bpm=100,
            genre="Pop",
            idea="Song A vision",
            chords="C Am F G",
        )
        b = _seed_doc(
            title="Edit Test B",
            key="G major",
            bpm=120,
            genre="Rock",
            idea="Song B vision",
            chords="G D Em C",
            template="pop",
        )
        ss = _library_session(a, b)
        set_active_document(ss, a)
        save_page_snapshot(ss, "composer")

        self.assertTrue(_open_edit(ss, str(a["id"])))
        _songs_to_studio_restore(ss)
        active_a = get_active_document(ss)
        assert active_a is not None
        self.assertEqual(str(active_a.get("id")), str(a["id"]))
        self.assertEqual(str(active_a.get("title")), "Edit Test A")
        self.assertEqual(int(playback_globals(active_a)["bpm"]), 100)
        self.assertEqual(playback_globals(active_a)["key_center"], "C")

        ss["_studio_active_page_id"] = "composer"
        ss["studio_page"] = "picker"
        self.assertTrue(_open_edit(ss, str(b["id"])))
        _songs_to_studio_restore(ss)
        active_b = get_active_document(ss)
        assert active_b is not None
        self.assertEqual(str(active_b.get("id")), str(b["id"]))
        self.assertEqual(str(active_b.get("title")), "Edit Test B")
        self.assertEqual(int(playback_globals(active_b)["bpm"]), 120)
        self.assertEqual(playback_globals(active_b)["key_center"], "G")
        self.assertNotEqual(str(active_a.get("id")), str(active_b.get("id")))
        self.assertNotEqual(len(ordered_sections(active_a)), len(ordered_sections(active_b)))

    def test_snapshot_restore_cannot_keep_last_active(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="A")
        b = _seed_doc(title="Edit Test B", key="G major", bpm=120, genre="Rock", idea="B")
        ss = _library_session(a, b)
        set_active_document(ss, a)
        save_page_snapshot(ss, "composer")
        self.assertTrue(_open_edit(ss, str(b["id"])))
        # Stale last-active snapshot (the previous bug): restore A after Edit B.
        snap = ss.setdefault("_studio_page_snapshots", {})
        composer_snap = dict(snap.get("composer") or {})
        composer_snap[COMPOSER_ACTIVE_KEY] = dict(a)
        snap["composer"] = composer_snap
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), str(b["id"]))
        self.assertEqual(str(active.get("title")), "Edit Test B")

    def test_practice_key_does_not_mutate_saved_composition(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="Home C")
        ss = _library_session(a)
        pick = composition_pick_key_for(a)
        ss["display_key"] = "D"
        ss["concert_key"] = "D"
        ss["practice_key_by_source"] = {pick: "D"}
        self.assertTrue(_open_edit(ss, pick))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(composition_home_key(active), "C")
        self.assertEqual(playback_globals(active)["key_center"], "C")
        stored = ss[COMPOSER_LIBRARY_KEY][str(a["id"])]
        self.assertEqual(composition_home_key(stored), "C")
        self.assertEqual(ss.get("display_key"), "D")
        self.assertEqual(ss.get("practice_key_by_source", {}).get(pick), "D")

    def test_partial_draft_opens_editable_state(self) -> None:
        draft = _seed_doc(
            title="Partial Draft",
            key="D minor",
            bpm=96,
            genre="Folk",
            idea="Unfinished lyrics",
            partial=True,
        )
        ss = _library_session(draft)
        self.assertTrue(_open_edit(ss, str(draft["id"])))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), str(draft["id"]))
        self.assertEqual(get_workflow_phase(active), "lyrics")
        verse = ordered_sections(active)[0]
        self.assertEqual(str((verse.get("lyrics") or {}).get("raw_text") or ""), "")
        self.assertFalse(active.get("review"))
        self.assertTrue(verse.get("chords"))
        self.assertTrue(section_has_melody(verse))
        self.assertEqual(ss.get("composer_needs_seed"), False)

    def test_full_document_restore(self) -> None:
        a = _seed_doc(
            title="Edit Test A",
            key="C major",
            bpm=100,
            genre="Pop",
            idea="Full restore vision",
            chords="C Am F G",
        )
        ss = _library_session(a)
        self.assertTrue(_open_edit(ss, str(a["id"])))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        pg = playback_globals(active)
        self.assertEqual(str(active.get("title")), "Edit Test A")
        self.assertEqual(str((active.get("metadata") or {}).get("style") or ""), "Pop")
        self.assertIn(
            "Full restore vision",
            str((active.get("metadata") or {}).get("description") or ""),
        )
        self.assertEqual(pg["key_center"], "C")
        self.assertEqual(int(pg["bpm"]), 100)
        self.assertEqual(pg["time_signature"], "4/4")
        secs = ordered_sections(active)
        self.assertGreaterEqual(len(secs), 2)
        names = [str(s.get("label") or s.get("label_variant") or s.get("type") or "") for s in secs]
        self.assertTrue(any("Verse" in n or str(s.get("type")) == "verse" for n, s in zip(names, secs)))
        verse = secs[0]
        self.assertTrue(verse.get("chords"))
        symbols = [str((c or {}).get("chord") or "") for c in (verse.get("chords") or []) if isinstance(c, dict)]
        self.assertIn("Dm", symbols)
        self.assertTrue(section_has_melody(verse))
        phrases = list(((verse.get("melody") or {}).get("phrases") or []))
        self.assertTrue(any("A4" in str(p.get("motif") or p.get("notes") or "") for p in phrases if isinstance(p, dict)))
        self.assertTrue(str((verse.get("lyrics") or {}).get("raw_text") or ""))
        self.assertEqual(str((active.get("review") or {}).get("notes") or ""), "Keep the hook")
        self.assertEqual(get_workflow_phase(active), "review")

    def test_edit_resave_updates_same_uuid_no_duplicate(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="A")
        b = _seed_doc(title="Edit Test B", key="G major", bpm=120, genre="Rock", idea="B")
        ss = _library_session(a, b)
        sid = str(a["id"])
        self.assertTrue(_open_edit(ss, sid))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        active["title"] = "Edit Test A (updated)"
        active["global"]["bpm"] = 108
        verse = ordered_sections(active)[0]
        chords = list(verse.get("chords") or [])
        if chords:
            chords[0]["chord"] = "Em"
            verse["chords"] = chords
        saved = save_document_to_library(ss, active)
        self.assertEqual(str(saved.get("id")), sid)
        rows = list_library_documents(ss)
        ids = [str(d.get("id")) for d in rows]
        self.assertEqual(ids.count(sid), 1)
        self.assertEqual(len(rows), 2)
        stored = ss[COMPOSER_LIBRARY_KEY][sid]
        self.assertEqual(str(stored.get("title")), "Edit Test A (updated)")
        self.assertEqual(int((stored.get("global") or {}).get("bpm") or 0), 108)
        self.assertEqual(str((ordered_sections(stored)[0].get("chords") or [{}])[0].get("chord")), "Em")

    def test_hub_and_library_edit_actions_use_helper(self) -> None:
        app_src = Path("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        self.assertIn("open_saved_composition_for_studio_edit", app_src)
        self.assertIn("resolve_songs_composition_edit_id", app_src)
        self.assertIn('help="Edit Composition"', app_src)
        self.assertIn("Edit composition", app_src)
        studio_src = Path("composition_studio_page.py").read_text(encoding="utf-8")
        self.assertIn("apply_pending_composer_studio_edit", studio_src)

    def test_hub_edit_resolves_active_pick_key(self) -> None:
        a = _seed_doc(title="Edit Test A", key="C major", bpm=100, genre="Pop", idea="A")
        b = _seed_doc(title="Edit Test B", key="G major", bpm=120, genre="Rock", idea="B")
        ss = _library_session(a, b)
        set_active_document(ss, a)
        save_page_snapshot(ss, "composer")
        ss["active_catalog_pick_key"] = composition_pick_key_for(b)
        ss["selected_song"] = composition_selected_song_record(b)
        doc_id = resolve_songs_composition_edit_id(ss)
        self.assertEqual(doc_id, str(b["id"]))
        self.assertTrue(_open_edit(ss, doc_id))
        _songs_to_studio_restore(ss)
        active = get_active_document(ss)
        assert active is not None
        self.assertEqual(str(active.get("id")), str(b["id"]))


class TestSongsCompositionStudioEditHarnessAppTest(unittest.TestCase):
    HARNESS = str(Path(__file__).resolve().parents[1] / "composition_songs_edit_handoff_harness.py")

    def test_edit_a_then_edit_b_in_harness(self) -> None:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(self.HARNESS, default_timeout=90)
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        id_a = str(at.session_state["_harness_id_a"])
        id_b = str(at.session_state["_harness_id_b"])
        self.assertTrue(id_a)
        self.assertTrue(id_b)
        self.assertNotEqual(id_a, id_b)

        at.button(key="harness_edit_a").click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        active = at.session_state["composer_active_document"]
        self.assertEqual(str(active.get("id") or ""), id_a)
        self.assertEqual(str(active.get("title") or ""), "Edit Test A")
        self.assertEqual(int((active.get("global") or {}).get("bpm") or 0), 100)
        self.assertEqual(str((active.get("global") or {}).get("original_key_center") or ""), "C")

        at.session_state["studio_page"] = "picker"
        at.session_state["_studio_active_page_id"] = "picker"
        at.run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        at.button(key="harness_edit_b").click().run(timeout=120)
        self.assertFalse(at.exception, msg=repr(at.exception))
        active_b = at.session_state["composer_active_document"]
        self.assertEqual(str(active_b.get("id") or ""), id_b)
        self.assertEqual(str(active_b.get("title") or ""), "Edit Test B")
        self.assertEqual(int((active_b.get("global") or {}).get("bpm") or 0), 120)
        self.assertEqual(str((active_b.get("global") or {}).get("original_key_center") or ""), "G")


if __name__ == "__main__":
    unittest.main()
