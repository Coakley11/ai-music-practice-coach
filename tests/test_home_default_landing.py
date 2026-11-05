"""Home is where a launch lands when nothing else decides - and nothing else changes.

Option A: a new user, or a workspace confirmed empty, opens on Home. Everything
that could already name a destination still names it - a returning user's saved
page, a persisted Backing or Custom session, a deep link, a pending upload, a
Creative return, history back/forward, and navigation the user performed in this
session. Arriving anywhere, Home included, leaves the musician's song, instrument
and keys untouched.
"""

import unittest

import app_ui
import studio_nav_state as sns
from studio_nav_history import STUDIO_PAGE_IDS


def _musical_state() -> dict:
    """A workspace with a song, an instrument and all three key forms committed."""
    return {
        "selected_song": {"title": "Blue Bossa", "key": "C minor", "genre": "Jazz"},
        "active_catalog_pick": "Jazz::Blue Bossa",
        "explicit_catalog_pick_committed": "Jazz::Blue Bossa",
        "instrument": "Alto Saxophone",
        "display_key": "F minor",
        "concert_key": "F minor",
        "concert_practice_key": "F minor",
        "custom_home_key": "F minor",
        "chart_in_instrument_key": True,
        "selected_transposing_instrument": "Alto saxophone (Eb)",
        "capo_fret": 2,
        "backing_owner": "catalog",
        "backing_context": {"source": "catalog"},
        "sections": {"A": ["Cm7", "F7"]},
        "song_sections": {"A": ["Cm7", "F7"]},
    }


class TestTheLandingPageIsHome(unittest.TestCase):
    def test_a_first_time_launch_opens_on_home(self):
        self.assertEqual(app_ui.ensure_studio_page({}), "home")

    def test_the_declared_default_is_home_everywhere_it_is_declared(self):
        import inspect

        self.assertEqual(sns.DEFAULT_STUDIO_PAGE, "home")
        self.assertEqual(
            inspect.signature(app_ui.ensure_studio_page).parameters["default"].default,
            "home",
        )
        self.assertEqual(
            inspect.signature(sns.bootstrap_studio_page_session)
            .parameters["default"].default,
            "home",
        )

    def test_a_restore_that_names_no_page_lands_on_home(self):
        page, why = sns.resolve_studio_page_for_restore({}, {})
        self.assertEqual(page, "home")
        self.assertEqual(why, "default")

    def test_home_is_a_real_page_id(self):
        self.assertIn(sns.DEFAULT_STUDIO_PAGE, STUDIO_PAGE_IDS)

    def test_home_and_practice_are_still_separate_destinations(self):
        self.assertNotEqual(sns.DEFAULT_STUDIO_PAGE, "practice")
        self.assertIn("practice", STUDIO_PAGE_IDS)
        self.assertIn("home", STUDIO_PAGE_IDS)


class TestHomeIsNotADeliberateDestination(unittest.TestCase):
    """Home must count as generic, or a cold start would suppress real restores."""

    def test_home_is_in_the_generic_startup_set(self):
        self.assertIn("home", sns._GENERIC_STARTUP_PAGES)

    def test_the_rest_of_the_generic_set_is_unchanged(self):
        self.assertEqual(
            sns._GENERIC_STARTUP_PAGES, frozenset({"", "picker", "practice", "home"})
        )

    def test_a_persisted_backing_session_still_beats_a_saved_home_page(self):
        page, why = sns.resolve_studio_page_for_restore(
            {}, {"music_workspace_state": {"studio_page": "home"},
                 "session": {"studio_page": "backing"}}
        )
        self.assertEqual(page, "backing")
        self.assertEqual(why, "persisted_session_backing")

    def test_a_persisted_custom_session_still_beats_a_saved_home_page(self):
        page, why = sns.resolve_studio_page_for_restore(
            {}, {"music_workspace_state": {"studio_page": "home"},
                 "session": {"studio_page": "custom"}}
        )
        self.assertEqual(page, "custom")
        self.assertEqual(why, "persisted_session_custom")

    def test_backing_and_custom_are_still_the_persisted_visit_pages(self):
        self.assertEqual(sns._PERSISTED_VISIT_PAGES, frozenset({"backing", "custom"}))


class TestAReturningUserKeepsTheirPage(unittest.TestCase):
    def test_a_saved_page_still_wins_over_home(self):
        for page in ("practice", "picker", "backing", "custom", "composer",
                     "creative", "multitrack", "analysis", "log"):
            with self.subTest(saved=page):
                got, why = sns.resolve_studio_page_for_restore(
                    {}, {"music_workspace_state": {"studio_page": page}}
                )
                self.assertEqual(got, page)
                self.assertEqual(why, "workspace_blob")

    def test_a_session_already_on_a_page_is_left_there(self):
        for page in ("practice", "backing", "custom", "multitrack", "creative"):
            with self.subTest(page=page):
                self.assertEqual(
                    app_ui.ensure_studio_page({"studio_page": page}), page
                )

    def test_a_refresh_keeps_the_page_it_had(self):
        """A refresh arrives as a fresh session over the same saved workspace."""
        for page in ("practice", "backing", "custom", "composer", "multitrack"):
            with self.subTest(page=page):
                got, _why = sns.resolve_studio_page_for_restore(
                    {}, {"music_workspace_state": {"studio_page": page}}
                )
                self.assertEqual(got, page)


class TestExplicitDestinationsStillWin(unittest.TestCase):
    def test_history_back_and_forward_is_preserved(self):
        page, why = sns.resolve_studio_page_for_restore(
            {"_studio_nav_from_history": True},
            {"music_workspace_state": {"studio_page": "custom"}},
            pre_restore_page="multitrack",
        )
        self.assertEqual(page, "multitrack")
        self.assertEqual(why, "history_nav_preserved")

    def test_navigation_the_user_performed_is_preserved(self):
        page, why = sns.resolve_studio_page_for_restore(
            {}, {"music_workspace_state": {"studio_page": "custom"}},
            pre_restore_page="backing", user_owns_page=True,
        )
        self.assertEqual(page, "backing")
        self.assertEqual(why, "user_page_preserved")

    def test_a_creative_return_handoff_is_preserved(self):
        page, why = sns.resolve_studio_page_for_restore(
            {"_creative_restore_from_backing": True}, {}
        )
        self.assertEqual(page, "creative")
        self.assertEqual(why, "creative_return_from_backing")

    def test_a_session_page_with_no_saved_blob_is_preserved(self):
        page, why = sns.resolve_studio_page_for_restore({}, {}, pre_restore_page="analysis")
        self.assertEqual(page, "analysis")
        self.assertEqual(why, "session_page_preserved")

    def test_a_deep_link_target_survives_the_landing_default(self):
        """A deep link sets studio_page before bootstrap; it must not be rewritten."""
        for page in ("backing", "composer", "creative", "multitrack", "log"):
            with self.subTest(page=page):
                session = {"studio_page": page}
                self.assertEqual(app_ui.ensure_studio_page(session), page)
                self.assertEqual(session["studio_page"], page)


class TestNothingMusicalMoves(unittest.TestCase):
    def test_landing_on_home_writes_no_musical_state(self):
        before = _musical_state()
        after = dict(before)
        self.assertEqual(app_ui.ensure_studio_page(after), "home")
        for key, value in before.items():
            self.assertEqual(after.get(key), value, f"{key} changed")

    def test_the_landing_default_only_adds_the_page(self):
        before = _musical_state()
        after = dict(before)
        app_ui.ensure_studio_page(after)
        added = {k for k in after if k not in before}
        self.assertTrue(
            added <= {"studio_page", "studio_nav_state", "_suite_page_user_nav"},
            f"unexpected keys written: {added}",
        )

    def test_a_returning_user_keeps_both_their_page_and_their_song(self):
        before = _musical_state()
        before["studio_page"] = "backing"
        after = dict(before)
        self.assertEqual(app_ui.ensure_studio_page(after), "backing")
        self.assertEqual(after["selected_song"]["title"], "Blue Bossa")
        self.assertEqual(after["display_key"], "F minor")
        self.assertEqual(after["instrument"], "Alto Saxophone")
        self.assertEqual(after["backing_owner"], "catalog")


class TestTheChangeStayedSmall(unittest.TestCase):
    """Guards against the global find-and-replace this change must not become."""

    def test_unrelated_practice_read_guards_were_left_alone(self):
        from pathlib import Path

        src = Path(sns.__file__).read_text(encoding="utf-8")
        # These are read-guards: the page is already set by the time they run.
        self.assertIn('_normalize_page(session.get("studio_page")) or "practice"', src)

    def test_the_practice_log_classification_was_not_touched(self):
        from practice_log_state import _STUDIO_PAGE_TO_PRACTICE_TYPE

        self.assertEqual(_STUDIO_PAGE_TO_PRACTICE_TYPE["practice"], "song practice")
        self.assertNotIn("home", _STUDIO_PAGE_TO_PRACTICE_TYPE)


if __name__ == "__main__":
    unittest.main()
