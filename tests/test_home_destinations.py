"""Home navigation: every card goes somewhere real, and nothing musical moves.

Visiting Home, or clicking through it, is a change of *view*. The song the
musician has loaded, the instrument they play, and the keys they read must come
out the other side untouched.
"""

import unittest

import home_destinations as hd
from studio_nav_history import STUDIO_PAGE_IDS, history_destination_id


def _musical_state() -> dict:
    """A session with a song, an instrument and all three key forms committed."""
    return {
        "studio_page": "home",
        "selected_song": {"title": "Blue Bossa", "key": "C minor", "genre": "Jazz"},
        "active_catalog_pick": "Jazz::Blue Bossa",
        "explicit_catalog_pick_committed": "Jazz::Blue Bossa",
        "instrument": "Alto Saxophone",
        "display_key": "F minor",
        "concert_key": "F minor",
        "concert_practice_key": "F minor",
        "chart_in_instrument_key": True,
        "selected_transposing_instrument": "Alto saxophone (Eb)",
        "capo_fret": 2,
        "backing_owner": "catalog",
        "sections": {"A": ["Cm7", "F7"]},
    }


class TestDestinationsAreReal(unittest.TestCase):
    def test_every_card_targets_an_existing_studio_page(self):
        for dest in hd.all_destinations():
            with self.subTest(card=dest.key):
                self.assertIn(dest.page, STUDIO_PAGE_IDS)

    def test_no_card_targets_home_itself(self):
        for dest in hd.all_destinations():
            self.assertNotEqual(dest.page, hd.HOME_PAGE_ID, dest.key)

    def test_card_keys_are_unique(self):
        keys = [d.key for d in hd.all_destinations()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_every_card_has_a_label_and_a_call_to_action(self):
        for dest in hd.all_destinations():
            with self.subTest(card=dest.key):
                self.assertTrue(dest.title.strip())
                self.assertTrue(dest.cta.strip())

    def test_the_named_workflows_are_all_reachable(self):
        pages = {d.page for d in hd.all_destinations()}
        for page in ("practice", "picker", "backing", "composer", "creative", "multitrack",
                     "custom", "analysis", "log"):
            self.assertIn(page, pages)


class TestMissionsAndCoachingAreDistinct(unittest.TestCase):
    def test_missions_and_song_aware_coaching_are_separate_destinations(self):
        missions = hd.destination_by_key("more_missions")
        coaching = hd.destination_by_key("more_sbi")
        self.assertIsNotNone(missions)
        self.assertIsNotNone(coaching)
        self.assertEqual(missions.page, "creative")
        self.assertEqual(coaching.page, "creative")
        self.assertNotEqual(missions.creative_dest, coaching.creative_dest)

    def test_missions_opens_the_missions_workspace(self):
        session = _musical_state()
        hd.apply_home_navigation(session, hd.destination_by_key("more_missions"),
                                 navigate=_fake_navigate)
        self.assertEqual(session["studio_page"], "creative")
        self.assertEqual(session["improv_intelligence_tab"], "Missions")
        self.assertEqual(history_destination_id(session), "creative::Missions")

    def test_song_aware_coaching_opens_song_based_improvisation(self):
        session = _musical_state()
        hd.apply_home_navigation(session, hd.destination_by_key("more_sbi"),
                                 navigate=_fake_navigate)
        self.assertEqual(session["studio_page"], "creative")
        self.assertEqual(session["improv_intelligence_tab"], "Song-Aware Coaching")
        self.assertEqual(session["improv_entry_mode"], "Song-Based Improvisation")
        self.assertEqual(history_destination_id(session), "creative::Song-Aware Coaching")

    def test_the_two_do_not_land_on_the_same_generic_page(self):
        a, b = _musical_state(), _musical_state()
        hd.apply_home_navigation(a, hd.destination_by_key("more_missions"), navigate=_fake_navigate)
        hd.apply_home_navigation(b, hd.destination_by_key("more_sbi"), navigate=_fake_navigate)
        self.assertNotEqual(history_destination_id(a), history_destination_id(b))


def _fake_navigate(session_state, page_id):
    changed = session_state.get("studio_page") != page_id
    session_state["studio_page"] = page_id
    return changed


class TestMusicalStateIsUntouched(unittest.TestCase):
    def test_no_card_writes_a_protected_key(self):
        for dest in hd.all_destinations():
            with self.subTest(card=dest.key):
                before = _musical_state()
                after = dict(before)
                hd.apply_home_navigation(after, dest, navigate=_fake_navigate)
                for key in hd.PROTECTED_STATE_KEYS:
                    self.assertEqual(
                        after.get(key), before.get(key),
                        f"{dest.key} changed protected key {key!r}",
                    )

    def test_navigation_only_adds_view_state(self):
        allowed = {
            "studio_page",
            "_home_catalog_browse",
            "_home_catalog_request",
            "_home_open_key_cycle",
            "workspace_genre_filters",
            "_genre_filters_user_touched",
            "improv_intelligence_tab",
            "creative_improv_intelligence_tab",
            "improv_entry_mode",
            "_improv_tab_user_touched",
            "_history_prev_entry_mode",
            "improv_intelligence_tab_for_render",
            "_history_live_creative_dest",
            "creative_lab_last_mode", "creative_lab_analysis_mode",
            "_creative_tab_tool_diag", "_creative_selector_overwrite_journal",
            "creative_workspace_state", "_creative_workspace_last_save_reason",
        }
        for dest in hd.all_destinations():
            with self.subTest(card=dest.key):
                before = _musical_state()
                after = dict(before)
                hd.apply_home_navigation(after, dest, navigate=_fake_navigate)
                touched = {k for k in set(before) | set(after)
                           if before.get(k) != after.get(k)}
                self.assertTrue(touched <= allowed, f"{dest.key} touched {touched - allowed}")


class TestGenreCards(unittest.TestCase):
    def test_a_genre_card_opens_browse_with_that_genre_ticked(self):
        session = _musical_state()
        hd.apply_home_navigation(session, hd.destination_by_key("discover_jazz"),
                                 navigate=_fake_navigate)
        self.assertEqual(session["studio_page"], "picker")
        self.assertEqual(session["_home_catalog_request"], "Jazz")

    def test_browse_everything_adds_no_filter(self):
        session = _musical_state()
        hd.apply_home_navigation(session, hd.BROWSE_ALL, navigate=_fake_navigate)
        self.assertEqual(session["studio_page"], "picker")
        self.assertEqual(session["_home_catalog_request"], "all")

    def test_a_genre_card_does_not_select_or_activate_a_song(self):
        session = _musical_state()
        hd.apply_home_navigation(session, hd.destination_by_key("discover_pop"),
                                 navigate=_fake_navigate)
        self.assertEqual(session["selected_song"]["title"], "Blue Bossa")
        self.assertEqual(session["active_catalog_pick"], "Jazz::Blue Bossa")

    def test_an_existing_genre_filter_is_not_duplicated(self):
        session = _musical_state()
        session["workspace_genre_filters"] = ["Jazz"]
        hd.apply_home_navigation(session, hd.destination_by_key("discover_jazz"),
                                 navigate=_fake_navigate)
        self.assertEqual(session["_home_catalog_request"], "Jazz")


class TestReturnValue(unittest.TestCase):
    def test_navigation_reports_whether_the_page_changed(self):
        session = _musical_state()
        dest = hd.destination_by_key("journey_practice")
        self.assertTrue(hd.apply_home_navigation(session, dest, navigate=_fake_navigate))
        self.assertFalse(hd.apply_home_navigation(session, dest, navigate=_fake_navigate))


if __name__ == "__main__":
    unittest.main()
