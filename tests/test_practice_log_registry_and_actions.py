"""Issues 4/5/6: one Practice Log category registry, new workflows, icon actions."""

from __future__ import annotations

import unittest

import practice_log_state as pls
import practice_log_ui as plu


class TestFocusAreaRegistry(unittest.TestCase):
    def test_original_entries_keep_their_position_and_new_ones_are_appended(self) -> None:
        original = ("tone", "timing/rhythm", "melody", "chords", "soloing/improv", "transcription",
                    "ear training", "lyrics/cues", "backing track", "performance", "technical exercise", "general")
        self.assertEqual(pls.FOCUS_AREAS[: len(original)], original)

    def test_every_requested_category_is_present(self) -> None:
        wanted = ["tone", "intonation", "articulation", "timing/rhythm", "tempo/metronome control", "melody", "chords",
                  "scales/modes", "arpeggios", "intervals", "technique/dexterity", "fingerings", "phrasing", "dynamics",
                  "expression/musicality", "soloing/improv", "pattern development", "ear training", "sight-reading",
                  "transcription", "lyrics/cues", "repertoire/memorization", "breath control", "embouchure",
                  "register/range", "vibrato", "tonguing", "picking/strumming", "rhythm comping", "bass lines",
                  "coordination", "performance preparation", "recording/take evaluation"]
        self.assertEqual([w for w in wanted if w not in pls.FOCUS_AREAS], [])

    def test_no_duplicates(self) -> None:
        self.assertEqual(len(set(pls.FOCUS_AREAS)), len(pls.FOCUS_AREAS))
        self.assertEqual(len(set(pls.PRACTICE_TYPES)), len(pls.PRACTICE_TYPES))

    def test_old_stored_values_still_normalise_to_themselves(self) -> None:
        for old in ("tone", "timing/rhythm", "technical exercise", "general", "Chords", "SOLOING/IMPROV"):
            got = pls._normalize_focus_area(old)
            self.assertIn(got.lower(), [a.lower() for a in pls.FOCUS_AREAS], old)
        self.assertEqual(pls._normalize_focus_area("chord transitions"), "chords")

    def test_new_values_round_trip(self) -> None:
        for area in pls.FOCUS_AREAS:
            self.assertEqual(pls._normalize_focus_area(area), area)

    def test_instrument_filtering_hides_irrelevant_categories_only_in_the_form(self) -> None:
        guitar = pls.focus_areas_for_instrument("Guitar")
        self.assertIn("picking/strumming", guitar)
        self.assertNotIn("embouchure", guitar)
        self.assertNotIn("breath control", guitar)
        sax = pls.focus_areas_for_instrument("Tenor Saxophone")
        self.assertIn("embouchure", sax)
        self.assertIn("tonguing", sax)
        self.assertNotIn("picking/strumming", sax)
        voice = pls.focus_areas_for_instrument("Voice")
        self.assertIn("breath control", voice)
        self.assertNotIn("embouchure", voice)
        self.assertEqual(pls.focus_areas_for_instrument(""), pls.FOCUS_AREAS)

    def test_editing_keeps_a_stored_value_even_if_the_instrument_changed(self) -> None:
        self.assertIn("embouchure", pls.focus_areas_for_instrument("Guitar", keep="embouchure"))

    def test_filters_use_the_full_registry(self) -> None:
        import inspect

        src = inspect.getsource(plu.render_filters)
        self.assertIn("list(FOCUS_AREAS)", src)
        self.assertIn("list(PRACTICE_TYPES)", src)


class TestPracticeTypes(unittest.TestCase):
    def test_new_workflows_are_available_and_old_ones_kept(self) -> None:
        for t in ("mission practice", "composition practice", "motif/pattern practice", "key cycling",
                  "song-aware coaching", "recording/multitrack", "song practice", "backing track",
                  "custom progression", "metronome", "karaoke/performance", "technique", "ear training"):
            self.assertIn(t, pls.PRACTICE_TYPES)

    def test_pages_map_to_the_matching_type(self) -> None:
        self.assertEqual(pls._STUDIO_PAGE_TO_PRACTICE_TYPE["composer"], "composition practice")
        self.assertEqual(pls._STUDIO_PAGE_TO_PRACTICE_TYPE["missions"], "mission practice")
        self.assertEqual(pls._STUDIO_PAGE_TO_PRACTICE_TYPE["backing"], "backing track")

    def test_legacy_modes_still_map(self) -> None:
        self.assertEqual(pls._normalize_practice_type("Song work"), "song practice")
        self.assertEqual(pls._normalize_practice_type("warmup"), "warmup")


class TestActionIcons(unittest.TestCase):
    def test_icons_are_the_apps_pencil_and_trash(self) -> None:
        self.assertEqual(plu.ICON_EDIT, "✏️")
        self.assertEqual(plu.ICON_DELETE, "\U0001f5d1️")

    def test_touch_target_css_is_at_least_44px(self) -> None:
        self.assertIn("min-height: 44px", plu._ACTION_ICON_CSS)
        self.assertIn("min-width: 44px", plu._ACTION_ICON_CSS)

    def test_actions_have_accessible_tooltips_and_still_edit_and_delete(self) -> None:
        import inspect

        src = inspect.getsource(plu.render_session_list)
        self.assertIn('help="Edit this session"', src)
        self.assertIn('help="Delete this session"', src)
        self.assertIn("delete_practice_log_entry(session_state, sid)", src)
        self.assertIn('session_state["_plog_edit_session_id"] = sid', src)




class TestActionsWork(unittest.TestCase):
    """Real render: icon buttons exist for each entry, Edit opens it, Delete removes it."""

    @staticmethod
    def _page() -> None:
        import streamlit as st

        from practice_log_ui import render_practice_log_page

        render_practice_log_page(st, st.session_state)

    def setUp(self) -> None:
        # In-memory log storage: nothing is read from or written to the data directory.
        from unittest import mock

        self.rows: list = []

        def _save(entries, st=None):
            self.rows[:] = [dict(e) for e in entries]
            return True, ""

        def _load(st=None):
            return [dict(e) for e in self.rows]

        for target, fn in (("practice_log_persistence.save_practice_logs", _save),
                           ("practice_log_persistence.load_practice_logs", _load)):
            p = mock.patch(target, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)

    def _at(self):
        from streamlit.testing.v1 import AppTest

        import practice_log_state as state

        at = AppTest.from_function(self._page, default_timeout=120)
        session: dict = {}
        entry = state.add_practice_log_entry(
            session, {"song": "Blues in F minor", "instrument": "Guitar", "duration_minutes": 20,
                      "focus_area": "phrasing", "practice_type": "mission practice"})
        for k, v in session.items():
            at.session_state[k] = v
        return at, str(entry.get("session_id") or entry.get("id") or "")

    def test_icon_buttons_render_with_the_stored_new_categories(self) -> None:
        at, sid = self._at()
        at.run()
        self.assertFalse(at.exception)
        labels = {b.key: b.label for b in at.button if str(b.key).startswith(("plog_edit_", "plog_delete_"))}
        self.assertEqual(sorted(labels.values()), sorted([plu.ICON_EDIT, plu.ICON_DELETE]))
        text = " ".join(str(m.value) for m in at.markdown)
        self.assertIn("phrasing", text)
        self.assertIn("mission practice", text)

    def test_edit_opens_the_entry(self) -> None:
        at, sid = self._at()
        at.run()
        [b for b in at.button if str(b.key).startswith("plog_edit_")][0].click().run()
        self.assertEqual(at.session_state["_plog_edit_session_id"], sid)

    def _two(self):
        from streamlit.testing.v1 import AppTest

        import practice_log_state as state

        at = AppTest.from_function(self._page, default_timeout=120)
        session: dict = {}
        a = state.add_practice_log_entry(session, {"song": "Keep Me", "instrument": "Guitar", "duration_minutes": 10,
                                                   "date": "2026-10-30"})
        b = state.add_practice_log_entry(session, {"song": "Delete Me", "instrument": "Guitar", "duration_minutes": 15,
                                                   "date": "2026-10-31"})
        for k, v in session.items():
            at.session_state[k] = v
        return at, str(a["session_id"]), str(b["session_id"])

    @staticmethod
    def _btn(at, key):
        return [b for b in at.button if b.key == key]

    def test_delete_asks_first_and_names_the_entry(self) -> None:
        at, keep, gone = self._two()
        at.run()
        self._btn(at, f"plog_delete_{gone}")[0].click().run()
        self.assertEqual(at.session_state[plu.PENDING_DELETE_KEY], gone)
        text = " ".join(str(w.value) for w in at.warning)
        self.assertIn("Delete Me", text)
        self.assertNotIn("Keep Me", text)
        self.assertTrue(self._btn(at, f"plog_delete_cancel_{gone}"))
        self.assertTrue(self._btn(at, f"plog_delete_confirm_{gone}"))
        # nothing was deleted yet
        self.assertEqual(len(self.rows), 2)

    def test_cancel_does_nothing(self) -> None:
        at, keep, gone = self._two()
        at.run()
        self._btn(at, f"plog_delete_{gone}")[0].click().run()
        self._btn(at, f"plog_delete_cancel_{gone}")[0].click().run()
        self.assertNotIn(plu.PENDING_DELETE_KEY, at.session_state)
        self.assertEqual(len(self.rows), 2)
        self.assertTrue(self._btn(at, f"plog_delete_{gone}"))

    def test_confirm_deletes_only_the_intended_entry(self) -> None:
        at, keep, gone = self._two()
        at.run()
        self._btn(at, f"plog_delete_{gone}")[0].click().run()
        self._btn(at, f"plog_delete_confirm_{gone}")[0].click().run()
        live = [r for r in self.rows if not r.get("deleted") and not r.get("_deleted") and not r.get("tombstone")]
        ids = {str(r.get("session_id")) for r in live}
        self.assertIn(keep, ids)
        self.assertNotIn(gone, ids)
        self.assertTrue(self._btn(at, f"plog_delete_{keep}"))
        self.assertFalse(self._btn(at, f"plog_delete_{gone}"))


if __name__ == "__main__":
    unittest.main()
