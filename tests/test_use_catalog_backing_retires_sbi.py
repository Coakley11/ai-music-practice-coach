"""'Use catalog song backing' from SBI Custom is a lasting ownership change.

Measured: SBI -> Custom (Blues in F minor) -> Backing -> Use catalog song
backing showed Catalog Shallow, but the sidebar kept Blues' Original Key, and
after leaving Backing and coming back the sidebar was Custom Progression again.
The switch cleared the backing context but not the SBI visit: the stored
Creative page snapshot still said "Custom progression". Entering Backing
re-applied that snapshot, and the restore predicates read it as a live SBI
Custom visit, rebuilding song_improv and the Custom sidebar overlay.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from backing_context import _persisted_backing_is_custom_sbi, _restore_should_rebind_custom_sbi
from source_session_state import (
    RESTORE_SBI_CUSTOM_SOURCE_KEY,
    SBI_PREVIEW_SOURCE_KEY,
    SBI_SONG_SOURCE_ACTIVE,
    SBI_SONG_SOURCE_CUSTOM,
    retire_sbi_custom_visit_markers,
)

_UI = (Path(__file__).resolve().parents[1] / "backing_context_ui.py").read_text(encoding="utf-8")


def _leftover_sbi_custom_visit() -> dict:
    """State after an SBI Custom Backing visit, as the browser trace found it."""
    creative_snapshot = {
        SBI_PREVIEW_SOURCE_KEY: SBI_SONG_SOURCE_CUSTOM,
        "improv_song_source": SBI_SONG_SOURCE_CUSTOM,
        RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
        "_nested_custom_sbi_backing": True,
        "_sbi_custom_sidebar_overlay": True,
    }
    return {
        "studio_page": "backing",
        SBI_PREVIEW_SOURCE_KEY: SBI_SONG_SOURCE_CUSTOM,
        "improv_song_source": SBI_SONG_SOURCE_CUSTOM,
        RESTORE_SBI_CUSTOM_SOURCE_KEY: True,
        "_nested_custom_sbi_backing": True,
        "_sbi_custom_sidebar_overlay": True,
        "_pending_improv_song_source": SBI_SONG_SOURCE_CUSTOM,
        "creative_workspace_state": dict(creative_snapshot),
        "creative_session": {"song_source": SBI_SONG_SOURCE_CUSTOM},
        "_studio_page_snapshots": {"creative": dict(creative_snapshot), "backing": {}},
    }


def _reenter_backing(session: dict) -> dict:
    """What a Backing page entry restores: the stored Creative snapshot's SBI fields."""
    snap = session["_studio_page_snapshots"]["creative"]
    out = dict(session)
    out[SBI_PREVIEW_SOURCE_KEY] = snap.get(SBI_PREVIEW_SOURCE_KEY)
    out["improv_song_source"] = snap.get("improv_song_source")
    out["_nested_custom_sbi_backing"] = snap.get("_nested_custom_sbi_backing")
    return out


class RetireSbiCustomVisitTests(unittest.TestCase):
    def test_leftover_visit_is_read_as_live_sbi_custom(self) -> None:
        """The failure: leftovers alone make the restore rebuild SBI Custom."""
        session = _reenter_backing(_leftover_sbi_custom_visit())
        self.assertTrue(_restore_should_rebind_custom_sbi(session))
        self.assertTrue(_persisted_backing_is_custom_sbi(session))

    def test_retired_visit_restores_as_catalog_after_reentry(self) -> None:
        session = _leftover_sbi_custom_visit()
        retire_sbi_custom_visit_markers(session)
        session = _reenter_backing(session)
        self.assertEqual(session[SBI_PREVIEW_SOURCE_KEY], SBI_SONG_SOURCE_ACTIVE)
        self.assertFalse(_restore_should_rebind_custom_sbi(session))
        self.assertFalse(_persisted_backing_is_custom_sbi(session))

    def test_every_persisted_copy_follows_active(self) -> None:
        session = _leftover_sbi_custom_visit()
        retire_sbi_custom_visit_markers(session)
        for where in (session, session["creative_workspace_state"], session["_studio_page_snapshots"]["creative"]):
            self.assertEqual(where[SBI_PREVIEW_SOURCE_KEY], SBI_SONG_SOURCE_ACTIVE)
            self.assertEqual(where["improv_song_source"], SBI_SONG_SOURCE_ACTIVE)
            self.assertFalse(where[RESTORE_SBI_CUSTOM_SOURCE_KEY])
            self.assertFalse(where["_nested_custom_sbi_backing"])
            self.assertNotIn("_sbi_custom_sidebar_overlay", where)
        self.assertNotIn("_pending_improv_song_source", session)
        self.assertEqual(session["creative_session"]["song_source"], SBI_SONG_SOURCE_ACTIVE)

    def test_retiring_does_not_touch_keys(self) -> None:
        session = _leftover_sbi_custom_visit()
        session.update({"display_key": "Fm", "concert_key": "Fm"})
        retire_sbi_custom_visit_markers(session)
        self.assertEqual((session["display_key"], session["concert_key"]), ("Fm", "Fm"))


class UseCatalogBackingHandlerTests(unittest.TestCase):
    def test_the_button_retires_the_visit_and_releases_specialized_backing(self) -> None:
        i = _UI.index("switch_to_catalog_from_custom(\n                    st,")
        block = _UI[i : _UI.index("st.rerun()", i)]
        self.assertIn("retire_sbi_custom_visit_markers(session)", block)
        self.assertIn('session["_backing_released_specialized_context"] = True', block)
        self.assertIn('session.pop("_backing_explicit_handoff_source", None)', block)
        self.assertIn("clear_pending_backing_workflow_handoff(session)", block)
        self.assertLess(block.index("retire_sbi_custom_visit_markers"), block.index("restore_regular_song_backing"))


if __name__ == "__main__":
    unittest.main()
