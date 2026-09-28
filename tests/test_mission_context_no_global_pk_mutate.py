"""Mission context construction must not mutate Catalog display_key on release/hydrate."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from song_catalog.catalog import format_pick_key
from songs.practice_key_state import PRACTICE_KEY_BY_SOURCE_KEY, get_practice_concert_key


PERFECT = format_pick_key("Pop", "Perfect — Ed Sheeran")
TRIAL_PICK = "custom::trial-song"


class _RejectDisplayKeyAssign(dict):
    """Session dict that fails if ``display_key`` is assigned after lock."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = False
        self.illegal_writes: list[str] = []

    def __setitem__(self, key, value):
        if self.locked and str(key) == "display_key":
            self.illegal_writes.append(f"display_key={value!r}")
            raise RuntimeError(f"StreamlitAPIException: cannot assign display_key after widget ({value!r})")
        return super().__setitem__(key, value)


def _catalog_session(**extra) -> dict:
    ss = {
        "studio_page": "picker",
        "active_music_source": "user_catalog",
        "active_catalog_pick_key": PERFECT,
        "selected_song": {
            "title": "Perfect",
            "artist": "Ed Sheeran",
            "key": "G",
            "pick_key": PERFECT,
        },
        "display_key": "D",
        "concert_key": "D",
        "original_key": "G",
        "instrument": "Guitar",
        PRACTICE_KEY_BY_SOURCE_KEY: {PERFECT: "D"},
        # Stale Mission residue — Catalog currently owns the surface.
        "improv_active_mission": "Outline chord tones on beat 1",
        "improv_mission_pick": "Outline chord tones on beat 1",
        "improv_intelligence_tab": "Missions",
        "creative_improv_intelligence_tab": "Missions",
        "ii_selected_chord": "G",
        "ii_selected_section": "Verse",
        "improv_mission_concert_key": "F",
        "_mission_backing_handoff_practice_key": "F",
        "_mission_backing_handoff_written_key": "G",
    }
    ss.update(extra)
    return ss


class TestBuildMissionContextNoGlobalPkMutate(unittest.TestCase):
    def test_build_mission_context_does_not_assign_display_or_concert(self) -> None:
        from backing_context import build_mission_context

        ss = _catalog_session()
        before_display = ss["display_key"]
        before_concert = ss["concert_key"]
        ctx = build_mission_context(ss)
        self.assertEqual(ctx.source, "mission")
        # Global Catalog Practice/display widgets must never be rewritten here —
        # even when sealed Mission handoff residue (F) exists beside Catalog D.
        self.assertEqual(ss["display_key"], before_display)
        self.assertEqual(ss["concert_key"], before_concert)
        self.assertNotEqual(ss["display_key"], "F")
        self.assertIsInstance(ctx.concert_key, str)
        self.assertTrue(bool(ctx.concert_key))

    def test_mission_sections_sync_does_not_mutate_catalog_display_key(self) -> None:
        from creative_session_state import (
            _mission_sections_from_session,
            sync_creative_session_from_session,
        )

        ss = _RejectDisplayKeyAssign(_catalog_session())
        ss.locked = True
        ss["_streamlit_widgets_locked_this_run"] = True
        before = ss["display_key"]
        try:
            sections = _mission_sections_from_session(ss)
            sync_creative_session_from_session(ss)
        except RuntimeError as exc:
            self.fail(f"late display_key write during Creative sync: {exc}")
        self.assertEqual(ss.illegal_writes, [])
        self.assertEqual(ss["display_key"], before)
        self.assertTrue(isinstance(sections, dict))


class TestCatalogHydrateWithStaleMission(unittest.TestCase):
    def test_hydrate_picker_release_does_not_mutate_mounted_display_key(self) -> None:
        from backing_source_navigation import hydrate_picker_source_for_page
        from music_source_ownership import (
            activate_catalog_ownership,
            reconcile_source_ownership,
        )

        ss = _RejectDisplayKeyAssign(_catalog_session())
        # Widget already mounted (global Practice Key selectbox).
        ss.locked = True
        ss["_streamlit_widgets_locked_this_run"] = True
        catalog_before = ss["display_key"]
        st_like = SimpleNamespace(session_state=ss)

        try:
            hydrate_picker_source_for_page(ss, st_like=st_like)
            reconcile_source_ownership(ss, st_like=st_like)
            activate_catalog_ownership(ss, st_like=st_like, preserve_practice_key=True)
        except RuntimeError as exc:
            self.fail(f"Streamlit-invalid display_key write: {exc}")

        self.assertEqual(ss.illegal_writes, [])
        # Catalog Practice remains authoritative (D), not Mission F.
        self.assertEqual(str(ss.get("display_key") or ""), catalog_before)
        self.assertNotEqual(str(ss.get("display_key") or ""), "F")
        sticky = str(get_practice_concert_key(ss, PERFECT) or "")
        self.assertIn(sticky, {"", "D", catalog_before})


class TestCreativeReleaseNoCatalogPkOverwrite(unittest.TestCase):
    def test_release_creative_backing_ownership_preserves_catalog_display(self) -> None:
        from backing_context import _release_creative_backing_ownership
        from music_source_ownership import _release_creative_transport_authority

        ss = _RejectDisplayKeyAssign(_catalog_session(display_key="E", concert_key="E"))
        ss[PRACTICE_KEY_BY_SOURCE_KEY] = {PERFECT: "E"}
        ss.locked = True
        ss["_streamlit_widgets_locked_this_run"] = True
        before = ss["display_key"]
        try:
            _release_creative_transport_authority(ss)
            _release_creative_backing_ownership(ss)
        except RuntimeError as exc:
            self.fail(f"release mutated display_key: {exc}")
        self.assertEqual(ss.illegal_writes, [])
        self.assertEqual(ss["display_key"], before)
        self.assertNotEqual(ss["display_key"], "F")


class TestIntentionalMissionActivationStillCommits(unittest.TestCase):
    def test_open_backing_mission_still_seals_practice_via_safe_path(self) -> None:
        from backing_context import build_mission_context, open_backing_from_creative
        from custom_progression_lab import CPL_ACTIVE_KEY, default_active_progression
        from mission_owner_contract import (
            HANDOFF_PRACTICE_KEY,
            HANDOFF_WRITTEN_KEY,
            stamp_mission_backing_handoff,
        )
        from songs.music_source import SOURCE_CUSTOM

        active = default_active_progression()
        active["id"] = "trial-song"
        active["name"] = "Trial Song"
        active["original_key_center"] = "D"
        active["practice_key"] = "F"
        ss = {
            "studio_page": "creative",
            "active_music_source": SOURCE_CUSTOM,
            "active_catalog_pick_key": TRIAL_PICK,
            CPL_ACTIVE_KEY: active,
            "display_key": "F",
            "concert_key": "F",
            "original_key": "D",
            "instrument": "Clarinet",
            "sax_type": "Bb Clarinet",
            "chart_in_instrument_key": True,
            PRACTICE_KEY_BY_SOURCE_KEY: {TRIAL_PICK: "F"},
            "improv_active_mission": "Outline chord tones",
            "improv_mission_pick": "Outline chord tones",
            "improv_intelligence_tab": "Missions",
            "ii_selected_chord": "F",
            "ii_selected_section": "Intro",
            "improv_mission_chord_options": ["F", "Bb", "C"],
            "improv_mission_concert_key": "F",
        }
        stamp_mission_backing_handoff(ss, concert_practice_key="F")
        self.assertEqual(ss.get(HANDOFF_PRACTICE_KEY), "F")
        # Builder must not touch display_key even when Mission owns Creative.
        before = ss["display_key"]
        ctx = build_mission_context(ss)
        self.assertEqual(ctx.concert_key, "F")
        self.assertEqual(ctx.display_key, "F")
        self.assertEqual(ss["display_key"], before)
        written = str(ss.get(HANDOFF_WRITTEN_KEY) or "")
        self.assertTrue(bool(written), "handoff must seal a written key")

        safe_calls: list[str] = []

        def _capture_safe(session, token, **_kwargs):
            safe_calls.append(str(token or ""))
            session["_pending_display_key"] = str(token or "")
            return str(token or "")

        st_like = MagicMock(session_state=ss)
        with patch(
            "session_widget_safe.safe_assign_display_key",
            side_effect=_capture_safe,
        ):
            open_backing_from_creative(ss, source="mission", st_like=st_like)
        self.assertEqual(str(ss.get("improv_mission_concert_key") or ""), "F")
        self.assertEqual(str(ss.get(HANDOFF_PRACTICE_KEY) or ""), "F")
        self.assertIn("F", safe_calls)


class TestMissionLeaveCatalogRestored(unittest.TestCase):
    def test_leave_mission_catalog_key_not_reclaimed_by_context_read(self) -> None:
        from backing_context import build_mission_context
        from creative_session_state import sync_creative_session_from_session

        ss = _catalog_session(display_key="D", concert_key="D")
        # Simulate leave: Catalog already restored before Creative snapshot sync.
        sync_creative_session_from_session(ss)
        build_mission_context(ss)
        self.assertEqual(ss["display_key"], "D")
        self.assertEqual(ss["concert_key"], "D")
        self.assertEqual(get_practice_concert_key(ss, PERFECT), "D")


if __name__ == "__main__":
    unittest.main()
