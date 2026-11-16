"""Circle of Fourths: a third Key Cycling interval on the existing engine."""

from __future__ import annotations

import unittest
from unittest import mock

import backing_key_cycle as kc
from music_theory import semitone_distance

UP = ["C", "F", "Bb", "Eb", "Ab", "Db", "F#", "B", "E", "A", "D", "G"]
DOWN = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"]


class TestCircleOfFourths(unittest.TestCase):
    def setUp(self) -> None:
        for p in (
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ss: dict = {"display_key": "C", "concert_key": "C"}

    def _start(self, direction: str, start: str = "C") -> None:
        self.ss["display_key"] = self.ss["concert_key"] = start
        kc.start_key_cycle(self.ss, start_key=start, interval=5, direction=direction)

    def test_step_names_and_sizes(self) -> None:
        self.assertEqual(kc.cycle_interval_for_step_name("fourth"), 5)
        self.assertEqual(kc.cycle_step_name_for_interval(5), "fourth")
        self.assertEqual(kc.CYCLE_STEP_LABELS["fourth"], "Circle of Fourths")
        self.assertEqual(kc.normalize_cycle_interval(5), 5)
        self.assertEqual(kc.normalize_cycle_interval(7), 1)  # unknown sizes stay semitone
        self.assertEqual(kc.cycle_sequence_length(interval=5), 12)
        self.assertEqual(kc.cycle_sequence_length(interval=2), 6)
        self.assertEqual(kc.cycle_sequence_length(interval=1), 12)

    def test_ascending_and_descending_sequences_default_spelling(self) -> None:
        self._start("up")
        self.assertEqual(kc.cycle_key_sequence(self.ss), UP)
        self._start("down")
        self.assertEqual(kc.cycle_key_sequence(self.ss), DOWN)

    def test_twelve_distinct_pitch_classes_each_plus_or_minus_five(self) -> None:
        for direction, step in (("up", 5), ("down", 7)):
            self._start(direction, start="A")
            seq = kc.cycle_key_sequence(self.ss)
            self.assertEqual(len(seq), 12)
            pcs = {semitone_distance("C", k) % 12 for k in seq}
            self.assertEqual(len(pcs), 12, seq)
            for a, b in zip(seq, seq[1:] + seq[:1]):
                self.assertEqual(semitone_distance(a, b) % 12, step, (direction, a, b))

    def test_minor_keys_keep_their_mode(self) -> None:
        self._start("up", start="Am")
        seq = kc.cycle_key_sequence(self.ss)
        self.assertTrue(all(k.endswith("m") for k in seq), seq)
        self.assertEqual(seq[:3], ["Am", "Dm", "Gm"])

    def test_manual_next_and_previous_walk_the_sequence_and_wrap(self) -> None:
        self._start("up")
        seen = [kc.temporary_playback_key(self.ss)]
        for _ in range(12):
            kc.advance_key_cycle_now(self.ss)
            seen.append(kc.temporary_playback_key(self.ss))
        self.assertEqual(seen[:12], UP)
        self.assertEqual(seen[12], "C")  # back to the start after twelve keys
        kc.previous_key_cycle_now(self.ss)
        self.assertEqual(kc.temporary_playback_key(self.ss), "G")
        self.assertEqual(kc.next_cycle_playback_key(self.ss), "C")
        self.assertEqual(kc.previous_cycle_playback_key(self.ss), "D")

    def test_natural_pass_stops_after_the_last_key(self) -> None:
        self._start("down")
        for _ in range(11):
            kc._advance_owner_cycle(self.ss, force=False, queue_continue=False, allow_wrap=False)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        kc._advance_owner_cycle(self.ss, force=False, queue_continue=False, allow_wrap=False)
        self.assertEqual(kc.temporary_playback_key(self.ss), "F")
        self.assertTrue(self.ss.get("_kc_cycle_finished_final"))

    def test_practice_key_never_written(self) -> None:
        self._start("up")
        for _ in range(5):
            kc.advance_key_cycle_now(self.ss)
        self.assertEqual(self.ss["display_key"], "C")
        self.assertEqual(kc.current_backing_owner_practice_key(self.ss), "C")

    def test_settings_change_to_fourths_keeps_saved_key_anchor(self) -> None:
        kc.start_key_cycle(self.ss, start_key="C", interval=1, direction="up")
        kc.advance_key_cycle_now(self.ss)
        kc.reset_key_cycle_position_for_settings(self.ss, interval=5, direction="up")
        data = kc.get_owner_cycle_session(self.ss)
        self.assertEqual(int(data["interval"]), 5)
        self.assertEqual(kc.temporary_playback_key(self.ss), "C")
        self.assertEqual(kc.cycle_key_sequence(self.ss), UP)

    def test_remembered_setting_and_status_line(self) -> None:
        self.ss[kc.BACKING_KEY_CYCLE_STEP_KEY] = "fourth"
        self.assertEqual(kc.cycle_step_semitones(self.ss), 5)
        self.ss[kc.BACKING_KEY_CYCLE_DIRECTION_KEY] = "down"
        self.assertEqual(kc.cycle_step_semitones(self.ss), -5)
        kc.start_key_cycle(self.ss)
        self.assertEqual(int(kc.get_owner_cycle_session(self.ss)["interval"]), 5)
        self.assertEqual(kc.remembered_key_cycle_settings(self.ss, kc.get_owner_cycle_session(self.ss)), ("fourth", "down"))
        self.assertTrue(any("Circle of Fourths" in line for line in kc.cycle_status_lines(self.ss)))

    def test_legacy_intervals_unchanged(self) -> None:
        kc.start_key_cycle(self.ss, start_key="C", interval=2, direction="up")
        self.assertEqual(kc.cycle_key_sequence(self.ss), ["C", "D", "E", "F#", "Ab", "Bb"])
        kc.start_key_cycle(self.ss, start_key="C", interval=1, direction="down")
        self.assertEqual(kc.cycle_key_sequence(self.ss)[:3], ["C", "B", "Bb"])


if __name__ == "__main__":
    unittest.main()
