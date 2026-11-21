"""Key Cycling in a Karaoke Set starts from Now Singing, not Now Editing (2026-11-21).

Browser run on 13de912d: the workspace's current (Now Editing) song was a Composition in C. A set
singing Blue Bossa (Catalog, saved performance key Am) turned Key Cycling On and it reset to C and
cycled C / F / Bb major over Blue Bossa's minor chart -- the cycle owner and base key were resolved
from the Composition. During a set the Now Singing entry owns the cycle's base key and its mode;
changing the editing song must not move the performing song's cycle.
"""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc

BLUE_BOSSA = "Jazz\x1fBlue Bossa — Kenny Dorham"
BLACKBIRD = "Pop\x1fBlackbird — The Beatles"
COMPOSITION = "composition::0d28766a-d906"


class KaraokeNowSingingOwnsCycleKey(unittest.TestCase):
    def setUp(self) -> None:
        self.composition_active = True
        self.composition_key = "C"
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch(
                "songs.music_source.composition_song_is_active",
                side_effect=lambda _s: self.composition_active,
            ),
            mock.patch(
                "composition_songs_bridge.resolve_composition_canonical_keys",
                side_effect=lambda _s: (self.composition_key, self.composition_key),
            ),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {
            "studio_page": "backing",
            "instrument": "Voice",
            # Now Editing: the Composition (sidebar Practice Key C).
            "active_catalog_pick_key": COMPOSITION,
            "display_key": "C",
            "concert_key": "C",
            "karaoke_queue": [
                {"entry_id": "e1", "pick_key": BLUE_BOSSA, "practice_key": "Am", "title": "Blue Bossa"},
                {"entry_id": "e2", "pick_key": BLACKBIRD, "practice_key": "E", "title": "Blackbird"},
            ],
            "karaoke_session_index": 0,
            "karaoke_session_active": True,
        }

    def _cycle(self) -> dict:
        data = kc.get_owner_cycle_session(self.ss)
        self.assertTrue(data and data.get("enabled"))
        return data

    def test_without_a_set_the_composition_owns_the_key(self) -> None:
        # Guard: the fixture really reproduces the Composition-as-owner state.
        self.ss["karaoke_session_active"] = False
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_COMPOSITION)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "C")

    def test_cycle_starts_from_the_now_singing_entry_key_and_mode(self) -> None:
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_CATALOG)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "Am")
        kc.start_key_cycle(self.ss, interval=5, direction="up")
        data = self._cycle()
        self.assertEqual(data.get("base_practice_key"), "Am")
        self.assertEqual(kc.temporary_playback_key(self.ss), "Am")
        self.assertEqual(kc.split_key_center(kc.temporary_playback_key(self.ss))[1], "minor")
        seq = kc.cycle_key_sequence(self.ss)
        self.assertEqual(seq[:3], ["Am", "Dm", "Gm"])

    def test_settings_reset_returns_to_the_entry_key_not_the_composition(self) -> None:
        # The observed write: reset_for_cycle_settings C -> C.
        kc.start_key_cycle(self.ss, interval=1, direction="up")
        kc.advance_key_cycle_now(self.ss)
        kc.reset_key_cycle_position_for_settings(self.ss, interval=5, direction="up")
        data = self._cycle()
        self.assertEqual(data.get("base_practice_key"), "Am")
        self.assertEqual(data.get("current_playback_key"), "Am")
        self.assertEqual(kc.cycle_key_sequence(self.ss)[:2], ["Am", "Dm"])

    def test_changing_the_editing_song_mid_set_keeps_the_performing_cycle(self) -> None:
        kc.start_key_cycle(self.ss, interval=5, direction="up")
        before = dict(self._cycle())
        # Now Editing moves: another Composition key, then a Catalog song in G.
        self.composition_key = "Eb"
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_CATALOG)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "Am")
        self.composition_active = False
        self.ss["active_catalog_pick_key"] = "Pop\x1fShallow"
        self.ss["display_key"] = self.ss["concert_key"] = "G"
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_CATALOG)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "Am")
        # The Backing run's song-follow check and Practice Key drift check leave it alone.
        self.assertFalse(kc.ensure_key_cycle_follows_active_song(self.ss))
        after = self._cycle()
        for field in ("cycle_id", "base_practice_key", "current_playback_key", "interval", "direction"):
            self.assertEqual(after.get(field), before.get(field), field)
        self.assertTrue(kc._keys_equivalent(after.get("base_practice_key"), kc.current_backing_owner_practice_key(self.ss)))
        # The saved setlist is untouched.
        self.assertEqual([e["practice_key"] for e in self.ss["karaoke_queue"]], ["Am", "E"])

    def test_next_entry_brings_its_own_key(self) -> None:
        self.ss["karaoke_session_index"] = 1
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "E")
        kc.start_key_cycle(self.ss, interval=5, direction="up")
        self.assertEqual(kc.temporary_playback_key(self.ss), "E")

    def test_composition_entry_cycles_under_the_composition_owner(self) -> None:
        self.ss["karaoke_queue"] = [{"entry_id": "c1", "pick_key": "composition::other", "practice_key": "Dm"}]
        self.composition_active = False
        self.ss["active_catalog_pick_key"] = BLUE_BOSSA
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_COMPOSITION)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "Dm")

    def test_end_set_gives_the_key_back_to_now_editing(self) -> None:
        self.ss["karaoke_session_active"] = False
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "C")
        self.ss["karaoke_session_active"] = True
        self.ss["instrument"] = "Piano"  # not a Voice set: ordinary Backing owner rules
        self.assertEqual(kc.resolve_cycle_owner(self.ss), kc.OWNER_COMPOSITION)
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "C")


if __name__ == "__main__":
    unittest.main()
