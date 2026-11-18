"""P0b: the shared Custom Backing Practice Key widget must not carry one Custom song's key into another.

Browser trace (synthetic): Blues (Fm) active, Trial (D) visited earlier -> opening Backing for Blues rewrote Blues' own
Practice Key to Trial's D and transposed its chords (Dm Em F Gm). Selecting Trial then became a half-applied handoff.
"""
from __future__ import annotations

import unittest
from unittest import mock

import backing_practice_key_control as K
import custom_progression_lab as L


def _song(sid, name, key, chords):
    return {"id": sid, "name": name, "original_key_center": key, "user_locked_home_key": True,
            "original_sections": {"Verse": [{"bars": 1, "chord": c} for c in chords]}}


TRIAL = _song("11111111-0000-0000-0000-0000000000aa", "Smoke Trial", "D", ["D", "Bm", "A", "G"])
BLUES = _song("22222222-0000-0000-0000-0000000000bb", "Smoke Blues", "Fm", ["Fm", "Gm", "Ab", "Bbm"])


def _session(active, widget_value, widget_pick):
    ss = {L.CPL_ACTIVE_KEY: dict(active), "studio_page": "backing"}
    if widget_value is not None:
        ss[K.WIDGET_CUSTOM] = widget_value
    if widget_pick is not None:
        ss[K.CUSTOM_BACKING_PK_WIDGET_PICK_KEY] = widget_pick
    return ss


class TestCustomBackingWidgetOwnership(unittest.TestCase):
    def _seed(self, ss, canonical):
        with mock.patch.object(K, "resolve_backing_pk_control_owner", return_value=K.OWNER_CUSTOM), mock.patch.object(
            K, "canonical_concert_key_for_owner", side_effect=lambda s, o="": canonical if s.get(K.WIDGET_CUSTOM) is None else s[K.WIDGET_CUSTOM]
        ):
            return K.seed_backing_practice_key_widget(ss)

    def test_a_widget_left_by_another_custom_song_does_not_win(self) -> None:
        from songs.music_source import custom_pick_key_for

        ss = _session(BLUES, "D", custom_pick_key_for(TRIAL))  # Trial's D is still in the shared widget
        want = self._seed(ss, "Fm")
        self.assertEqual(want, "Fm")
        self.assertEqual(ss[K.WIDGET_CUSTOM], "Fm")
        self.assertEqual(ss["display_key"], "Fm")
        self.assertEqual(ss[K.CUSTOM_BACKING_PK_WIDGET_PICK_KEY], custom_pick_key_for(BLUES))

    def test_the_same_song_keeps_the_users_own_value(self) -> None:
        from songs.music_source import custom_pick_key_for

        ss = _session(BLUES, "Gm", custom_pick_key_for(BLUES))  # the user picked Gm for THIS song
        want = self._seed(ss, "Fm")
        self.assertEqual(want, "Gm")
        self.assertEqual(ss[K.WIDGET_CUSTOM], "Gm")

    def test_first_open_after_a_restart_starts_at_the_songs_canonical_key(self) -> None:
        ss = _session(BLUES, "D", None)  # no owner recorded (new process): the leftover is not trusted
        self.assertEqual(self._seed(ss, "Fm"), "Fm")

    def test_other_owners_are_untouched(self) -> None:
        ss = {L.CPL_ACTIVE_KEY: dict(BLUES), K.WIDGET_CATALOG: "G"}
        with mock.patch.object(K, "resolve_backing_pk_control_owner", return_value=K.OWNER_CATALOG), mock.patch.object(
            K, "canonical_concert_key_for_owner", return_value="G"
        ):
            K.seed_backing_practice_key_widget(ss)
        self.assertNotIn(K.CUSTOM_BACKING_PK_WIDGET_PICK_KEY, ss)

    def test_a_restored_visit_key_and_sbi_widget_from_the_previous_song_are_dropped_too(self) -> None:
        """A new session: the persisted page snapshot / Creative mirror brought back Trial's D into the SBI keys."""
        from songs.music_source import custom_pick_key_for

        ss = _session(BLUES, None, None)  # no owner recorded: nothing proves these values belong to Blues
        ss[K.WIDGET_SBI_CUSTOM] = "D"
        ss["_sbi_custom_visit_pk"] = "D"
        seen = {}

        def canon(s, o=""):
            seen["sbi"], seen["visit"] = s.get(K.WIDGET_SBI_CUSTOM), s.get("_sbi_custom_visit_pk")
            return "Fm"

        with mock.patch.object(K, "resolve_backing_pk_control_owner", return_value=K.OWNER_CUSTOM), mock.patch.object(
            K, "canonical_concert_key_for_owner", side_effect=canon
        ):
            K.seed_backing_practice_key_widget(ss)
        self.assertEqual(seen, {"sbi": None, "visit": None})  # gone BEFORE the canonical key is resolved
        self.assertEqual(ss[K.CUSTOM_BACKING_PK_WIDGET_PICK_KEY], custom_pick_key_for(BLUES))

    def test_the_same_song_keeps_its_sbi_values(self) -> None:
        from songs.music_source import custom_pick_key_for

        ss = _session(BLUES, "Gm", custom_pick_key_for(BLUES))
        ss[K.WIDGET_SBI_CUSTOM] = "Gm"
        ss["_sbi_custom_visit_pk"] = "Gm"
        with mock.patch.object(K, "resolve_backing_pk_control_owner", return_value=K.OWNER_CUSTOM), mock.patch.object(
            K, "canonical_concert_key_for_owner", return_value="Fm"
        ):
            K.seed_backing_practice_key_widget(ss)
        self.assertEqual((ss[K.WIDGET_SBI_CUSTOM], ss["_sbi_custom_visit_pk"]), ("Gm", "Gm"))

    def test_the_sbi_custom_owner_is_covered_too(self) -> None:
        """Backing opened from a Custom song seals the sbi_custom owner: that is the real path in the browser."""
        from songs.music_source import custom_pick_key_for

        ss = _session(BLUES, None, custom_pick_key_for(TRIAL))  # Trial was the last song seeded
        ss[K.WIDGET_SBI_CUSTOM] = "D"
        ss["_sbi_custom_visit_pk"] = "D"
        seen = {}

        def canon(s, o=""):
            seen["sbi"], seen["visit"] = s.get(K.WIDGET_SBI_CUSTOM), s.get("_sbi_custom_visit_pk")
            return "Fm"

        with mock.patch.object(K, "resolve_backing_pk_control_owner", return_value=K.OWNER_SBI_CUSTOM), mock.patch.object(
            K, "canonical_concert_key_for_owner", side_effect=canon
        ):
            want = K.seed_backing_practice_key_widget(ss)
        self.assertEqual(seen, {"sbi": None, "visit": None})
        self.assertEqual(want, "Fm")
        self.assertEqual(ss[K.WIDGET_SBI_CUSTOM], "Fm")


if __name__ == "__main__":
    unittest.main()
