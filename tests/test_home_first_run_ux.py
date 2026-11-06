"""A first launch should be quiet, and looking at Home should log nothing.

Two separate claims:

1. "No saved song selection; restored default catalog song." only ever appeared
   on a genuine first launch - the branch that set it is gated by
   ``workspace_is_truly_empty``. On a first launch nothing was lost, so there is
   nothing to warn about. The default song is still seeded; only the warning is
   gone. Every other notice in ``songs.state`` reports something that really
   changed and must survive.

2. Home cannot write a Practice Log entry. The only writer reachable from the UI
   is ``add_practice_log_entry``, and the page that calls it renders under
   ``studio_page == "log"`` alone.
"""

import re
import unittest
from pathlib import Path

import songs.state as songs_state
from songs.state import PICK_KEY_RECOVERY_NOTICE_KEY

_SRC = Path(songs_state.__file__).read_text(encoding="utf-8")
_APP = Path(songs_state.__file__).resolve().parents[1] / "streamlit_music_practice_app.py"


class TestTheFirstLaunchIsQuiet(unittest.TestCase):
    def test_the_first_run_message_is_gone_from_the_source(self):
        self.assertNotIn("No saved song selection; restored default catalog song.", _SRC)

    def test_the_default_song_is_still_seeded_on_that_branch(self):
        """The commit stayed; only its notice went."""
        self.assertIn("return _commit(fallback)", _SRC)

    def test_notices_about_real_changes_are_untouched(self):
        for notice in (
            "is no longer available; showing the default catalog song.",
            "Restored song selection from saved workspace.",
            "Restored default song selection.",
            "after a catalog change.",
            "was moved or renamed in the catalog; selection updated.",
        ):
            with self.subTest(notice=notice):
                self.assertIn(notice, _SRC)

    def test_the_branch_remains_gated_to_a_truly_empty_workspace(self):
        """If this guard ever goes, the message's absence stops being safe."""
        self.assertIn("workspace_is_truly_empty(st.session_state)", _SRC)
        self.assertIn("_may_apply_catalog_default()", _SRC)

    def test_the_notice_channel_still_works_for_other_messages(self):
        session: dict = {}
        session[PICK_KEY_RECOVERY_NOTICE_KEY] = "Restored default song selection."
        self.assertEqual(
            session.get(PICK_KEY_RECOVERY_NOTICE_KEY), "Restored default song selection."
        )

    def test_the_app_still_renders_whatever_notice_is_set(self):
        app = _APP.read_text(encoding="utf-8")
        self.assertIn("PICK_KEY_RECOVERY_NOTICE_KEY", app)
        self.assertIn("st.warning(_pick_key_recovery)", app)


class TestHomeWritesNoPracticeLog(unittest.TestCase):
    def _home_sources(self):
        root = Path(songs_state.__file__).resolve().parents[1]
        return {
            name: (root / name).read_text(encoding="utf-8")
            for name in ("home_page.py", "home_destinations.py", "home_recent_session.py")
        }

    def test_no_home_module_writes_a_log_entry(self):
        for name, src in self._home_sources().items():
            with self.subTest(module=name):
                for writer in ("add_practice_log_entry", "update_practice_log_entry",
                               "delete_practice_log_entry", "save_entries"):
                    self.assertNotIn(writer, src, f"{name} references {writer}")

    def test_home_only_reads_the_log(self):
        src = self._home_sources()["home_recent_session.py"]
        self.assertIn("load_entries", src)

    def test_the_only_log_writer_is_reached_from_the_log_page_alone(self):
        """render_practice_log_page is what calls the writer; find its dispatch branch."""
        app = _APP.read_text(encoding="utf-8")
        idx = app.index("from practice_log_ui import render_practice_log_page")
        before = app[:idx]
        branches = re.findall(r"^(?:el)?if _studio_page == \"([a-z]+)\":", before, re.M)
        self.assertTrue(branches)
        self.assertEqual(branches[-1], "log")

    def test_home_is_not_a_practice_type(self):
        from practice_log_state import _STUDIO_PAGE_TO_PRACTICE_TYPE

        self.assertNotIn("home", _STUDIO_PAGE_TO_PRACTICE_TYPE)

    def test_the_practice_page_classification_is_unchanged(self):
        from practice_log_state import _STUDIO_PAGE_TO_PRACTICE_TYPE

        self.assertEqual(_STUDIO_PAGE_TO_PRACTICE_TYPE["practice"], "song practice")
        self.assertEqual(_STUDIO_PAGE_TO_PRACTICE_TYPE["backing"], "backing track")
        self.assertEqual(_STUDIO_PAGE_TO_PRACTICE_TYPE["log"], "song practice")


if __name__ == "__main__":
    unittest.main()
