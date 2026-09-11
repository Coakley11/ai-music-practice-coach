"""H3 refresh owner restore: persisted Backing page vs default picker.

A saved Jam UUID is not enough to force Jam Backing. The user must have
been on that Backing page when refresh occurred.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from music_persistent_state import apply_music_disk_state
from studio_nav_state import (
    _studio_page_from_blob,
    prepare_studio_nav,
    resolve_studio_page_for_restore,
)

JAM_ID = "21a3456b-bce0-4343-90c4-af567aaeda07"
EB_SECTIONS = {
    "A (Bossa Nova)": ["Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
    "B (Bossa Nova)": ["Fm7", "Bb7", "Gm7", "C7"],
}


def _jam_blob_dict() -> dict:
    return {
        "workflow_owner": "jam_session_generator",
        "workflow_session_id": JAM_ID,
        "generated_session_id": JAM_ID,
        "keys": {
            "practice_tonic": "Eb",
            "practice_mode": "major",
            "original_tonic": "C",
            "original_mode": "major",
            "key_owner": "jam_session_generator",
        },
        "section_map": EB_SECTIONS,
        "style": "Bossa Nova",
        "groove": "Ballad",
        "tempo_bpm": 70,
        "source_type": "generated",
    }


def _entry_jam_session(*, studio_page: str) -> dict:
    return {
        "studio_page": studio_page,
        "display_key": "Eb",
        "improv_jam_key": "Eb",
        "_jam_session_generator_session_id": JAM_ID,
        "_backing_explicit_handoff_source": "entry_jam",
        "backing_context": {
            "source": "entry_jam",
            "source_label": "Entry & Jam",
            "key": "Eb",
            "display_key": "Eb",
            "concert_key": "Eb",
            "bpm": 70,
            "style": "Bossa Nova",
            "groove": "Ballad",
        },
        "improv_jam_session": {
            "id": JAM_ID,
            "key": "Eb",
            "style": "Bossa Nova",
            "bpm": 70,
            "sections": EB_SECTIONS,
        },
    }


def _cws_with_jam() -> dict:
    return {
        "music_workflow_state_v1": {
            "store": {
                "blobs": {f"jam_session_generator|{JAM_ID}": _jam_blob_dict()},
            }
        }
    }


def _blob(
    *,
    session_page: str,
    nav_page: str,
    workspace_page: str,
    core_page: str,
    backing_source: str = "entry_jam",
) -> dict:
    session = _entry_jam_session(studio_page=session_page)
    if backing_source != "entry_jam":
        session["backing_context"] = {
            "source": backing_source,
            "source_label": "Catalog song",
            "key": "G",
            "display_key": "G",
            "concert_key": "G",
            "song_title": "Say",
        }
        session["_backing_explicit_handoff_source"] = backing_source
        session["display_key"] = "G"
    return {
        "studio_nav_state": {"studio_page": nav_page, "page": nav_page},
        "music_workspace_state": {"studio_page": workspace_page, "page": workspace_page},
        "core": {"studio_page": core_page, "display_key": session.get("display_key")},
        "session": session,
        "creative_workspace_state": _cws_with_jam(),
    }


def _hydrate(blob: dict) -> dict:
    st = MagicMock()
    st.session_state = {}
    apply_music_disk_state(st, blob, song_picker_catalog={}, song_library={})
    prepare_studio_nav(st.session_state)
    return st.session_state


class TestH3RefreshOwnerRestore(unittest.TestCase):
    def test_a_persisted_backing_entry_jam_stays_backing(self) -> None:
        blob = _blob(
            session_page="backing",
            nav_page="backing",
            workspace_page="backing",
            core_page="backing",
        )
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "backing")
        ctx = ss.get("backing_context") if isinstance(ss.get("backing_context"), dict) else {}
        self.assertEqual(str(ctx.get("source") or ""), "entry_jam")
        self.assertEqual(ss.get("_jam_session_generator_session_id"), JAM_ID)

    def test_b_jam_uuid_with_picker_page_stays_picker(self) -> None:
        blob = _blob(
            session_page="picker",
            nav_page="picker",
            workspace_page="picker",
            core_page="picker",
        )
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "picker")
        self.assertNotEqual(source, "persisted_session_backing")
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "picker")
        self.assertEqual(ss.get("_jam_session_generator_session_id"), JAM_ID)

    def test_c_entry_jam_eb_hydrate_derives_eb_context(self) -> None:
        blob = _blob(
            session_page="backing",
            nav_page="backing",
            workspace_page="backing",
            core_page="backing",
        )
        ss = _hydrate(blob)
        from backing_context import build_entry_jam_context
        from source_session_state import bind_sidebar_practice_key_to_backing_owner

        ctx = build_entry_jam_context(ss)
        self.assertEqual(str(getattr(ctx, "source", "") or ""), "entry_jam")
        tok = str(
            getattr(ctx, "concert_key", "")
            or getattr(ctx, "display_key", "")
            or getattr(ctx, "key", "")
            or ""
        )
        self.assertTrue(tok.startswith("Eb"), tok)
        bound = bind_sidebar_practice_key_to_backing_owner(
            type("St", (), {"session_state": ss})(),
            ss,
        )
        self.assertTrue(str(bound).startswith("Eb"), bound)
        self.assertTrue(str(ss.get("display_key") or "").startswith("Eb"))

    def test_d_generic_picker_cannot_overwrite_persisted_backing(self) -> None:
        blob = _blob(
            session_page="backing",
            nav_page="backing",
            workspace_page="picker",
            core_page="picker",
        )
        self.assertEqual(_studio_page_from_blob(blob), "backing")
        page, source = resolve_studio_page_for_restore({}, blob)
        self.assertEqual(page, "backing")
        self.assertEqual(source, "persisted_session_backing")
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "backing")
        self.assertNotEqual(ss.get("studio_page"), "picker")

    def test_e_catalog_return_refresh_stays_catalog_not_jam(self) -> None:
        blob = _blob(
            session_page="backing",
            nav_page="backing",
            workspace_page="backing",
            core_page="backing",
            backing_source="regular_song",
        )
        ss = _hydrate(blob)
        self.assertEqual(ss.get("studio_page"), "backing")
        ctx = ss.get("backing_context") if isinstance(ss.get("backing_context"), dict) else {}
        self.assertEqual(str(ctx.get("source") or ""), "regular_song")
        self.assertEqual(ss.get("_jam_session_generator_session_id"), JAM_ID)
        jam = ss.get("improv_jam_session") if isinstance(ss.get("improv_jam_session"), dict) else {}
        self.assertEqual(str(jam.get("key") or ""), "Eb")
        self.assertEqual(ss.get("studio_page"), "backing")

    def test_prepare_live_backing_beats_stale_canonical_picker(self) -> None:
        session = {
            "studio_page": "backing",
            "studio_nav_state": {"studio_page": "picker", "last_write_reason": "page_change"},
        }
        page = prepare_studio_nav(session)
        self.assertEqual(page, "backing")
        self.assertEqual(session["studio_page"], "backing")
        self.assertEqual(session["studio_nav_state"]["studio_page"], "backing")


if __name__ == "__main__":
    unittest.main()
