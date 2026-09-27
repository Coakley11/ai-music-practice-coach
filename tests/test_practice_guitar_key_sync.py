"""Practice-page Guitar sounding-key authority — one coherent current key.

Daniel's bug: Practice / Concert Key, sidebar Sounding Key, unified Transpose
helpers, Guitar capo helper, capo fret, and "Backing track plays in" must all
describe the same current Practice sounding key — never Song Original Key.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock


class _Ui:
    def __init__(self) -> None:
        self.markdowns: list[str] = []

    def markdown(self, body, **_kwargs):
        self.markdowns.append(str(body))

    def checkbox(self, *_args, **kwargs):
        key = kwargs.get("key")
        if key and key not in self._session:
            self._session[key] = kwargs.get("value", False)
        return bool(self._session.get(key)) if key else False

    def selectbox(self, *_args, **kwargs):
        key = kwargs.get("key")
        options = _args[1] if len(_args) > 1 else kwargs.get("options") or []
        if key and key not in self._session and options:
            self._session[key] = options[0]
        return self._session.get(key, options[0] if options else "")

    def caption(self, *_args, **_kwargs):
        return None


class TestPracticeGuitarKeySync(unittest.TestCase):
    def test_practice_d_shape_c_helper_not_original_g(self) -> None:
        """Case 1: Practice D + Shape C → sounding D / capo 2, never G / 7."""
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            CAPO_SOUNDING_KEY,
            build_capo_context,
            capo_status_banner_html,
            sync_capo_from_practice_display_key,
        )
        from instrument_transposition import transpose_helpers_facts

        session = {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "C",
            # Stale blob remnant from Song Original Key G (the bug).
            CAPO_SOUNDING_KEY: "G",
            "active_song_state": {
                CAPO_ENABLED_KEY: True,
                CAPO_SHAPE_KEY: "C",
                CAPO_SOUNDING_KEY: "G",
                "pick_key": "Pop\x1fPerfect",
                "display_key": "D",
            },
            "active_catalog_pick_key": "Pop\x1fPerfect",
            "display_key": "D",
            "instrument": "Guitar",
        }
        sync_capo_from_practice_display_key(session, "D")
        session[CAPO_SHAPE_KEY] = "C"

        facts = transpose_helpers_facts(
            session,
            original_key="G",
            concert_key="D",
            instrument="Guitar",
        )
        fact_map = dict(facts)
        self.assertEqual(fact_map["Original Key"], "G")
        self.assertEqual(fact_map["Practice / Concert Key"], "D")
        self.assertEqual(fact_map["Shape Key"], "C")
        self.assertEqual(fact_map["Capo Fret (derived)"], "2")

        ctx = build_capo_context(
            session,
            {"Verse": ["D", "A", "Bm", "G"]},
            concert_key="D",
            instrument="Guitar",
        )
        self.assertEqual(ctx.sounding_key, "D")
        self.assertEqual(ctx.shape_key, "C")
        self.assertEqual(ctx.capo_fret, 2)
        self.assertEqual(session[CAPO_SOUNDING_KEY], "D")
        banner = capo_status_banner_html(ctx)
        self.assertIn("Actual sounding key:</strong> D", banner)
        self.assertIn("Backing track plays in:</strong> D", banner)
        self.assertIn("2nd fret", banner)
        self.assertNotIn("Actual sounding key:</strong> G", banner)
        self.assertNotIn("7th fret", banner)

    def test_sidebar_sounding_follows_practice_not_sticky_d(self) -> None:
        """Case 2: fixed-family E must move sidebar Sounding Key off stale D."""
        from guitar_capo import (
            CAPO_ENABLED_KEY,
            CAPO_SHAPE_KEY,
            CAPO_SOUNDING_KEY,
            render_guitar_capo_sidebar,
        )
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY

        session = {
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "E",
            CAPO_SOUNDING_KEY: "D",
            "active_catalog_pick_key": "Pop\x1fPerfect",
            "instrument": "Guitar",
            PRACTICE_KEY_BY_SOURCE_KEY: {"Pop\x1fPerfect": "D"},
            "display_key": "E",
        }
        ui = _Ui()
        ui._session = session  # type: ignore[attr-defined]
        # Patch widget helpers so sidebar can render without Streamlit.
        with mock.patch.object(ui, "checkbox", return_value=True), mock.patch.object(
            ui, "selectbox", return_value="E"
        ):
            render_guitar_capo_sidebar(
                ui,
                session,
                practice_display_key="E",
                persist_st=SimpleNamespace(session_state=session),
            )
        joined = "\n".join(ui.markdowns)
        self.assertIn("Sounding Key:</strong> E", joined)
        self.assertNotIn("Sounding Key:</strong> D", joined)
        self.assertEqual(session[CAPO_SOUNDING_KEY], "E")

    def test_fixed_family_e_syncs_sticky_and_capo_sounding(self) -> None:
        """Fixed family selection writes the same Practice path Guitar surfaces read."""
        from guitar_capo import CAPO_ENABLED_KEY, CAPO_SHAPE_KEY, CAPO_SOUNDING_KEY, build_capo_context
        from practice_key_mode import (
            FIXED_PRACTICE_KEY_FAMILY_ID,
            MODE_FIXED,
            PRACTICE_KEY_MODE_KEY,
            on_practice_key_family_change,
        )
        from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key

        session = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            FIXED_PRACTICE_KEY_FAMILY_ID: "D|B",
            "active_catalog_pick_key": "Pop\x1fPerfect",
            "display_key": "D",
            CAPO_ENABLED_KEY: True,
            CAPO_SHAPE_KEY: "C",
            CAPO_SOUNDING_KEY: "D",
            PRACTICE_KEY_BY_SOURCE_KEY: {"Pop\x1fPerfect": "D"},
            "practice_panel_fixed_practice_key": "E|C#",
        }
        # Simulate the family widget committing E|C#.
        session["practice_panel_fixed_practice_key"] = "E|C#"
        on_practice_key_family_change(session, original_key="G", st_like=None)
        self.assertEqual(session.get(FIXED_PRACTICE_KEY_FAMILY_ID), "E|C#")
        sticky = str(get_practice_concert_key(session, "Pop\x1fPerfect") or "")
        self.assertEqual(sticky, "E")
        self.assertEqual(session[CAPO_SOUNDING_KEY], "E")

        # Shape may still be C from prior capo choice; sounding must be E → capo 4.
        session[CAPO_SHAPE_KEY] = "C"
        ctx = build_capo_context(
            session,
            {"Verse": ["E", "B", "C#m", "A"]},
            concert_key="E",
            instrument="Guitar",
        )
        self.assertEqual(ctx.sounding_key, "E")
        self.assertEqual(ctx.capo_fret, 4)

        # Shape E + sounding E → open.
        session[CAPO_SHAPE_KEY] = "E"
        ctx2 = build_capo_context(
            session,
            {"Verse": ["E", "B", "C#m", "A"]},
            concert_key="E",
            instrument="Guitar",
        )
        self.assertEqual(ctx2.sounding_key, "E")
        self.assertEqual(ctx2.shape_key, "E")
        self.assertEqual(ctx2.capo_fret, 0)

    def test_capo_invariants_d_c_e_e_e_c(self) -> None:
        from guitar_capo import capo_fret_for_shape

        self.assertEqual(capo_fret_for_shape("D", "C"), 2)
        self.assertEqual(capo_fret_for_shape("E", "E"), 0)
        self.assertEqual(capo_fret_for_shape("E", "C"), 4)

    def test_ownership_safety_fixed_family_does_not_swap_song(self) -> None:
        from practice_key_mode import (
            FIXED_PRACTICE_KEY_FAMILY_ID,
            MODE_FIXED,
            PRACTICE_KEY_MODE_KEY,
            on_practice_key_family_change,
        )

        session = {
            PRACTICE_KEY_MODE_KEY: MODE_FIXED,
            FIXED_PRACTICE_KEY_FAMILY_ID: "D|B",
            "practice_panel_fixed_practice_key": "E|C#",
            "active_catalog_pick_key": "Pop\x1fPerfect",
            "active_music_source": "user_catalog",
            "display_key": "D",
            "studio_page": "practice",
            "nav_history": [{"page": "practice"}],
        }
        before_pick = session["active_catalog_pick_key"]
        before_source = session["active_music_source"]
        before_hist_len = len(session["nav_history"])
        on_practice_key_family_change(session, original_key="G", st_like=None)
        self.assertEqual(session["active_catalog_pick_key"], before_pick)
        self.assertEqual(session["active_music_source"], before_source)
        self.assertEqual(len(session["nav_history"]), before_hist_len)
        self.assertEqual(session.get("studio_page"), "practice")


if __name__ == "__main__":
    unittest.main()
