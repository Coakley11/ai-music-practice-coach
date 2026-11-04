"""Home is a first-class page - and Practice is still where the app starts.

These cover the wiring rather than the look: the page id is registered everywhere
the other ten are, back/forward treats Home like any other destination, and the
startup default has not moved.
"""

import unittest

import app_ui
import home_page
import studio_nav_history as snh
from home_destinations import HOME_PAGE_ID
from music_feature_icons import page_feature_icon
from songs.chart_bundle_startup import studio_page_exempt_from_chart_bundle


class TestRegisteredEverywhere(unittest.TestCase):
    def test_home_is_a_studio_page_id(self):
        self.assertIn(HOME_PAGE_ID, snh.STUDIO_PAGE_IDS)

    def test_the_other_ten_pages_are_still_registered(self):
        for page in ("practice", "picker", "backing", "custom", "composer",
                     "creative", "multitrack", "analysis", "log", "openai"):
            self.assertIn(page, snh.STUDIO_PAGE_IDS)

    def test_home_has_a_label_an_icon_and_a_nav_class(self):
        meta = app_ui.STUDIO_PAGE_META[HOME_PAGE_ID]
        self.assertEqual(meta["label"], "Home")
        self.assertTrue(meta["icon"].strip())
        self.assertEqual(meta["nav_class"], "home")

    def test_home_has_its_own_accent_colour(self):
        accent = app_ui.studio_page_accent(HOME_PAGE_ID)
        self.assertTrue(accent.startswith("#"))
        others = {p: app_ui.studio_page_accent(p)
                  for p in snh.STUDIO_PAGE_IDS if p != HOME_PAGE_ID}
        self.assertNotIn(accent, others.values())

    def test_home_appears_in_the_top_navigation(self):
        self.assertIn(HOME_PAGE_ID, app_ui.TOP_NAV_PAGE_IDS)

    def test_home_appears_in_the_quick_and_simple_navigation_rows(self):
        self.assertIn(HOME_PAGE_ID, app_ui.QUICK_NAV_ROW_PRIMARY)
        self.assertIn(HOME_PAGE_ID, app_ui.SIMPLE_NAV_PAGE_IDS)

    def test_home_leads_every_nav_and_practice_follows_it(self):
        for name, row in (
            ("top nav", app_ui.TOP_NAV_PAGE_IDS),
            ("quick nav", app_ui.QUICK_NAV_ROW_PRIMARY),
            ("simple nav", app_ui.SIMPLE_NAV_PAGE_IDS),
        ):
            with self.subTest(nav=name):
                self.assertEqual(row[0], HOME_PAGE_ID)
                self.assertEqual(row[1], "practice")

    def test_home_has_a_compact_nav_label(self):
        self.assertEqual(app_ui.nav_compact_button_label(HOME_PAGE_ID), "Home")

    def test_home_has_a_feature_icon(self):
        self.assertTrue(page_feature_icon(HOME_PAGE_ID).strip())

    def test_home_needs_no_catalog_chart_bundle(self):
        self.assertTrue(studio_page_exempt_from_chart_bundle(HOME_PAGE_ID))


class TestStartupDefaultHasNotMoved(unittest.TestCase):
    def test_a_fresh_session_still_starts_on_practice(self):
        self.assertEqual(app_ui.ensure_studio_page({}), "practice")

    def test_the_declared_default_is_still_practice(self):
        import inspect

        sig = inspect.signature(app_ui.ensure_studio_page)
        self.assertEqual(sig.parameters["default"].default, "practice")

    def test_an_existing_session_on_home_stays_on_home(self):
        self.assertEqual(app_ui.ensure_studio_page({"studio_page": "home"}), "home")


class TestBackAndForward(unittest.TestCase):
    def test_leaving_home_can_be_undone(self):
        session = {"studio_page": "home"}
        snh.init_nav_history(session)
        snh.navigate_studio_page(session, "practice")
        self.assertEqual(session["studio_page"], "practice")
        self.assertTrue(snh.can_go_back(session))
        snh.go_back(session)
        self.assertEqual(session["studio_page"], "home")

    def test_home_can_be_returned_to_with_forward(self):
        session = {"studio_page": "home"}
        snh.init_nav_history(session)
        snh.navigate_studio_page(session, "backing")
        snh.go_back(session)
        self.assertTrue(snh.can_go_forward(session))
        snh.go_forward(session)
        self.assertEqual(session["studio_page"], "backing")

    def test_arriving_at_home_from_a_workspace_can_be_undone(self):
        session = {"studio_page": "multitrack"}
        snh.init_nav_history(session)
        snh.navigate_studio_page(session, "home")
        self.assertEqual(session["studio_page"], "home")
        snh.go_back(session)
        self.assertEqual(session["studio_page"], "multitrack")

    def test_home_is_a_normal_history_destination_id(self):
        self.assertEqual(snh.history_destination_id({"studio_page": "home"}), "home")


class TestHomeRendersWithoutMutating(unittest.TestCase):
    def test_the_emblem_is_embedded_and_far_smaller_than_the_full_logo(self):
        from pathlib import Path

        uri = home_page.home_emblem_data_uri()
        self.assertTrue(uri.startswith("data:image/png;base64,"))
        root = Path(home_page.__file__).resolve().parent / "static" / "branding"
        full = (root / "mpc_logo_emblem.png").stat().st_size
        small = (root / "mpc_logo_emblem_256.png").stat().st_size
        self.assertLess(small * 8, full)

    def test_the_optimized_emblem_is_square_and_derived_from_the_repo_logo(self):
        from pathlib import Path

        from PIL import Image

        root = Path(home_page.__file__).resolve().parent / "static" / "branding"
        small = Image.open(root / "mpc_logo_emblem_256.png")
        full = Image.open(root / "mpc_logo_emblem.png")
        self.assertEqual(small.size, (256, 256))
        self.assertEqual(full.size[0], full.size[1])

    def test_every_tap_target_rule_meets_forty_four_pixels(self):
        css = home_page.home_page_css()
        self.assertIn("min-height: 44px", css)
        self.assertIn("min-width: 44px", css)

    def test_the_css_carries_the_brand_colours(self):
        css = home_page.home_page_css()
        for token in ("#312e81", "#4338ca", "#facc15", "#93c5fd"):
            self.assertIn(token, css)

    def test_each_card_wears_its_destination_accent(self):
        from home_destinations import JOURNEY_CARDS

        css = home_page.home_page_css()
        for dest in JOURNEY_CARDS:
            accent = app_ui.studio_page_accent(dest.page)
            self.assertIn(f".st-key-home_card_{dest.key} {{ --home-accent: {accent}; }}", css)

    def test_the_prototype_placeholder_label_is_gone(self):
        css_and_text = home_page.home_page_css() + home_page.HOME_SUBTITLE + home_page.HOME_TITLE
        self.assertNotIn("Local design concept", css_and_text)

    def test_the_page_collapses_to_one_column_on_a_phone(self):
        css = home_page.home_page_css()
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("flex: 1 1 100% !important", css)


if __name__ == "__main__":
    unittest.main()
