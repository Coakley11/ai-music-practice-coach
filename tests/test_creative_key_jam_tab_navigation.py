"""Jam Session D major must stay authoritative across Missions / Harmony / Return."""

from __future__ import annotations

import unittest
from typing import Any

from creative_key_sync import (
    entry_jam_practice_key_authority_active,
    resolve_creative_tab_practice_key_token,
)
from improvisation_intelligence_ui import _authoritative_practice_chart_key, _coherent_improv_key_pair
from improvisation_intelligence import ImprovSessionContext
from music_workflow_pending_creative_return import (
    PENDING_CREATIVE_RETURN_KEY,
    consume_pending_creative_return_handoff,
)
from music_workflow_song_practice import ensure_missions_parent_practice_key_hydrated
from musical_context_authority import (
    catalog_song_should_own_sidebar_practice_key,
    resolve_authoritative_practice_key,
    sidebar_key_list_mode,
)


def _jam_d_major_session(*, tab: str = "Live Coach") -> dict[str, Any]:
    return {
        "studio_page": "creative",
        "improv_entry_mode": "Jam Session Generator",
        "improv_jam_key": "D",
        "improv_generated_sections": {"Jam": ["D", "G", "A", "D"]},
        "improv_intelligence_tab": tab,
        "active_catalog_pick_key": "Jewish|Hevenu",
        "song": "Hevenu Shalom Aleichem",
        "display_key": "D",
        "concert_key": "D",
        "home_sections": {"Melody A": ["C#m", "G#7"], "Melody B": ["C#m", "G#7"]},
    }


class TestJamKeyAcrossCreativeTabs(unittest.TestCase):
    def test_entry_jam_active_on_missions_tab(self) -> None:
        session = _jam_d_major_session(tab="Missions")
        self.assertTrue(entry_jam_practice_key_authority_active(session))
        self.assertFalse(catalog_song_should_own_sidebar_practice_key(session))
        self.assertEqual(resolve_creative_tab_practice_key_token(session), "D")
        self.assertEqual(sidebar_key_list_mode(session), "major")

    def test_missions_hydrate_does_not_pull_catalog_minor_blob(self) -> None:
        session = _jam_d_major_session(tab="Missions")
        session["display_key"] = "C#m"
        session["concert_key"] = "C#m"
        ensure_missions_parent_practice_key_hydrated(session)
        self.assertEqual(str(session.get("display_key") or ""), "D")
        self.assertEqual(_authoritative_practice_chart_key(session, "C#m"), "D")

    def test_harmony_coherent_key_pair(self) -> None:
        session = _jam_d_major_session(tab="Harmony Map")
        ctx = ImprovSessionContext(
            song_title="Hevenu",
            artist="",
            key_center="C#m",
            display_key="C#m",
            instrument="Guitar",
            level="Intermediate",
            focus="Improvisation",
            sections={},
        )
        kc, dk = _coherent_improv_key_pair(session, ctx)
        self.assertEqual(kc, "D")
        self.assertEqual(dk, "D")

    def test_return_to_creative_preserves_jam_key_over_song_blob(self) -> None:
        session = _jam_d_major_session(tab="Missions")
        session["display_key"] = "C#m"
        session[PENDING_CREATIVE_RETURN_KEY] = {
            "request_seq": 1,
            "consume_token": "t1",
            "sealed_context": {"display_key": "D", "concert_key": "D"},
        }
        with unittest.mock.patch(
            "backing_source_navigation.prepare_return_to_backing_source",
            return_value="creative",
        ):
            phase = consume_pending_creative_return_handoff(session)
        self.assertEqual(phase, "applied")
        self.assertEqual(str(session.get("display_key") or ""), "D")
        pk = resolve_authoritative_practice_key(session)
        self.assertEqual(pk.practice_mode, "major")
        self.assertEqual(pk.practice_key_token, "D")


if __name__ == "__main__":
    unittest.main()
