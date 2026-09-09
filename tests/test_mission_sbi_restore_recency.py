"""Restore recency: newer Mission Backing outranks leftover SBI metadata.

Full-history gate-12 reboot can persist:

  backing_context.source = mission
  persist_mission = true
  creative_session.tool_type = mission
  leftover improv_entry_mode = Song-Based Improvisation

from_dict used to drop ``mission`` (missing from the entry-mode map) and remap
the session to song_based_improvisation. Startup then rebuilt song_improv over
the newer Mission owner.

The reverse remains true: a newer explicit SBI Backing owner restores SBI.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from backing_context import get_backing_context, hydrate_backing_context_after_restore
from backing_source_navigation import hydrate_backing_source_for_page
from creative_session_state import CREATIVE_SESSION_KEY, CreativeSession, get_creative_session
from song_catalog.catalog import format_pick_key


SHAPE = format_pick_key("Pop", "Shape of You — Ed Sheeran")
CLOCKS = format_pick_key("Pop", "Clocks — Coldplay")


def _mission_ctx_blob() -> dict:
    return {
        "source": "mission",
        "source_label": "Mission Backing Jam",
        "song_title": "Shape of You",
        "active_song_id": SHAPE,
        "bound_pick_key": SHAPE,
        "mission_id": "Improvise using only chord tones",
        "key": "Fm",
        "display_key": "Fm",
        "concert_key": "Fm",
        "bpm": 96,
        "progression": ["Cm"],
        "section": "Verse",
    }


def _sbi_ctx_blob() -> dict:
    return {
        "source": "song_improv",
        "source_label": "Song-Based Improvisation",
        "song_title": "Shape of You",
        "active_song_id": SHAPE,
        "bound_pick_key": SHAPE,
        "sbi_source_owner": "Active song",
        "key": "E",
        "display_key": "E",
        "concert_key": "E",
        "bpm": 100,
        "progression": ["Bm", "Em", "G"],
        "entry_mode": "Song-Based Improvisation",
        "mode_label": "Song-Based Improvisation",
    }


def _full_history_mission_reboot_session(*, pick: str = SHAPE) -> dict:
    """Persisted Mission Backing plus leftover SBI radio from earlier visits."""
    return {
        "studio_page": "backing",
        "active_catalog_pick_key": pick,
        "selected_song": {
            "title": "Shape of You — Ed Sheeran",
            "pick_key": SHAPE,
            "key": "Bm",
        },
        "display_key": "Fm",
        "concert_key": "Fm",
        "improv_entry_mode": "Song-Based Improvisation",
        "improv_intelligence_tab": "Missions",
        "improv_song_source": "Active song",
        "sbi_preview_source": "Active song",
        "improv_active_mission": "Improvise using only chord tones",
        "improv_mission_concert_key": "Fm",
        "_restore_sbi_custom_source": True,
        "_backing_explicit_handoff_source": "mission",
        "_backing_source_preference": "creative",
        CREATIVE_SESSION_KEY: {
            "session_id": "mission-blob",
            "tool_type": "mission",
            "entry_mode": "Song-Based Improvisation",
            "song_source": "Active song",
            "concert_key": "Fm",
            "display_key": "Fm",
            "mission_id": "Improvise using only chord tones",
            "intelligence_tab": "Missions",
            "sections": {"Verse": ["Cm"]},
        },
        "backing_context": _mission_ctx_blob(),
    }


class MissionSbiRestoreRecencyTests(unittest.TestCase):
    def test_from_dict_keeps_mission_despite_leftover_sbi_entry_mode(self) -> None:
        sess = CreativeSession.from_dict(
            {
                "tool_type": "mission",
                "entry_mode": "Song-Based Improvisation",
                "mission_id": "Improvise using only chord tones",
                "intelligence_tab": "Missions",
            }
        )
        assert sess is not None
        self.assertEqual(sess.tool_type, "mission")
        self.assertEqual(sess.entry_mode, "Song-Based Improvisation")
        live = {CREATIVE_SESSION_KEY: sess.to_dict()}
        got = get_creative_session(live)
        assert got is not None
        self.assertEqual(got.tool_type, "mission")

    def test_newer_mission_owner_outranks_older_sbi_radio_on_restore(self) -> None:
        session = _full_history_mission_reboot_session()
        hydrate_backing_context_after_restore(session)
        hydrate_backing_source_for_page(
            session, st_like=SimpleNamespace(session_state=session)
        )
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "mission")
        self.assertEqual(session.get("_backing_explicit_handoff_source"), "mission")

    def test_invalid_mission_ctx_rebuilds_mission_not_leftover_sbi(self) -> None:
        """Catalog pick mismatch must not rebuild leftover Song-Based Improvisation."""
        session = _full_history_mission_reboot_session(pick=CLOCKS)
        session["selected_song"] = {
            "title": "Clocks — Coldplay",
            "pick_key": CLOCKS,
            "key": "Eb",
        }
        hydrate_backing_context_after_restore(session)
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "mission")
        got = get_creative_session(session)
        assert got is not None
        self.assertEqual(got.tool_type, "mission")

    def test_newer_sbi_owner_outranks_older_mission_creative_session(self) -> None:
        session = _full_history_mission_reboot_session()
        session["_backing_explicit_handoff_source"] = "song_improv"
        session["backing_context"] = _sbi_ctx_blob()
        session[CREATIVE_SESSION_KEY] = {
            "session_id": "stale-mission",
            "tool_type": "mission",
            "entry_mode": "Song-Based Improvisation",
            "mission_id": "Improvise using only chord tones",
            "intelligence_tab": "Missions",
        }
        hydrate_backing_context_after_restore(session)
        hydrate_backing_source_for_page(
            session, st_like=SimpleNamespace(session_state=session)
        )
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "song_improv")
        self.assertEqual(session.get("_backing_explicit_handoff_source"), "song_improv")

    def test_restore_last_without_specialized_handoff_class_keeps_mission(self) -> None:
        session = _full_history_mission_reboot_session()
        session.pop("_backing_entry_class", None)
        session.pop("_backing_open_intent", None)
        hydrate_backing_source_for_page(
            session, st_like=SimpleNamespace(session_state=session)
        )
        ctx = get_backing_context(session)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.source, "mission")


if __name__ == "__main__":
    unittest.main()
