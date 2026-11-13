"""Key Cycling console readouts and the Live Mission Example.

Covers the brief's worked examples: alto saxophone (written Gm7 over concert
Bb, Circle of Fourths up -> written Cm7 C-Eb-G-Bb over concert Eb), concert
pitch (no redundant Sounding line), Guitar Shape mode (fixed Am7 shape, capo
moves, sounding chord moves) and Key Spelling (labels follow the preference,
position does not move).
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import backing_key_cycle as kc
from improvisation_missions import MISSION_PRACTICE_LICK_KEY
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY
from key_cycle_console import console_model, exercise_type_for_mission, live_mission_model

ALTO = "Alto saxophone (Eb)"


def _lick(*, chart_key: str, chord: str, concert_chord: str, notes: list[str], midi: list[int],
          concert_notes: list[str], instrument: str) -> dict:
    return {
        "mission_title": "Improvise using only chord tones",
        "instrument": instrument,
        "bpm": 96,
        "level": "Intermediate",
        "key_center": chart_key,
        "chord": chord,
        "_concert_chord": concert_chord,
        "motif": {
            "notes": list(notes),
            "midi": list(midi),
            "rhythm": "q q q q",
            "chord": chord,
            "_concert_chord": concert_chord,
            "_concert_notes": list(concert_notes),
            "_projected_display_key": chart_key,
        },
    }


class _MissionCycleCase(unittest.TestCase):
    base = "C"

    def setUp(self) -> None:
        patches = [
            mock.patch("monetization_entitlements.can_use", return_value=True),
            mock.patch.object(kc, "persist_key_cycle_position", return_value=True),
            mock.patch.object(kc, "resolve_cycle_owner", return_value=kc.OWNER_MISSION),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _session(self, **extra) -> dict:
        ss = {
            "studio_page": "backing",
            "improv_mission_concert_key": self.base,
            "display_key": self.base,
            "concert_key": self.base,
            "instrument": "Piano",
        }
        ss.update(extra)
        return ss

    def _start(self, ss: dict, *, interval: int = 5, direction: str = "up") -> None:
        kc.start_key_cycle(ss, start_key=self.base, interval=interval, direction=direction)
        self.assertTrue(kc.is_cycle_active(ss))

    def _model(self, ss: dict, status: str = "playing") -> dict:
        return console_model(ss, current_concert=kc.temporary_playback_key(ss), status=status)


class TestAltoSaxophoneMission(_MissionCycleCase):
    base = "Bb"

    def _alto(self) -> dict:
        ss = self._session(
            instrument="Saxophone",
            show_chart_in_instrument_key=True,
            **{SELECTED_TRANSPOSING_INSTRUMENT_KEY: ALTO},
        )
        # Written Gm7 (chord tones G Bb D F) sounds as concert Bbm7 on alto.
        ss[MISSION_PRACTICE_LICK_KEY] = _lick(
            chart_key="G", chord="Gm7", concert_chord="Bbm7",
            notes=["G", "Bb", "D", "F"], midi=[67, 70, 74, 77],
            concert_notes=["Bb", "Db", "F", "Ab"], instrument="Saxophone",
        )
        return ss

    def test_first_position_and_next_written_keys(self) -> None:
        ss = self._alto()
        self._start(ss)
        m = self._model(ss)
        self.assertEqual(m["mode"], "written")
        self.assertEqual(m["current_label"], "G major")
        self.assertEqual(m["next_label"], "C major")
        self.assertTrue(m["show_sounding"])
        self.assertEqual(m["sounding_label"], "Bb major")
        self.assertEqual(m["interval_label"], "Circle of Fourths")
        live = live_mission_model(ss, current_concert=kc.temporary_playback_key(ss))
        self.assertIsNotNone(live)
        self.assertEqual(live["chords_written"], ["Gm7"])
        self.assertEqual(live["motif"]["notes"], ["G", "Bb", "D", "F"])
        self.assertEqual(live["exercise_type"], "Chord Tones")

    def test_next_moves_example_to_c_minor_seven_and_original_stays(self) -> None:
        ss = self._alto()
        original = copy.deepcopy(ss[MISSION_PRACTICE_LICK_KEY])
        self._start(ss)
        kc.advance_key_cycle_now(ss)
        self.assertEqual(kc.temporary_playback_key(ss), "Eb")
        m = self._model(ss)
        self.assertEqual((m["current_label"], m["next_label"], m["sounding_label"]),
                         ("C major", "F major", "Eb major"))
        live = live_mission_model(ss, current_concert="Eb")
        self.assertEqual(live["chords_written"], ["Cm7"])
        self.assertEqual(live["chords_sounding"], ["Ebm7"])
        self.assertEqual(live["motif"]["notes"], ["C", "Eb", "G", "Bb"])
        self.assertIn("K:C", live["abc"].replace(" ", ""))
        # Rhythm and the exercise are the Mission's own.
        self.assertEqual(live["rhythm"], "q q q q")
        # The stored (normal card) example is untouched.
        self.assertEqual(ss[MISSION_PRACTICE_LICK_KEY], original)
        # Previous returns to G / Gm7.
        kc.previous_key_cycle_now(ss)
        live = live_mission_model(ss, current_concert=kc.temporary_playback_key(ss))
        self.assertEqual(live["chords_written"], ["Gm7"])
        self.assertEqual(live["motif"]["notes"], ["G", "Bb", "D", "F"])

    def test_full_cycle_never_drifts(self) -> None:
        ss = self._alto()
        self._start(ss)
        for _ in range(12):
            kc.advance_key_cycle_now(ss)
        self.assertEqual(kc.temporary_playback_key(ss), "Bb")
        live = live_mission_model(ss, current_concert="Bb")
        self.assertEqual(live["motif"]["notes"], ["G", "Bb", "D", "F"])
        self.assertEqual(live["motif"]["midi"], [67, 70, 74, 77])


class TestConcertPitchMission(_MissionCycleCase):
    base = "C"

    def test_no_redundant_sounding_line_and_harmonic_relationship(self) -> None:
        ss = self._session()
        # Dm7 practised in C: in F it becomes Gm7 (ii stays ii), not Fm7.
        ss[MISSION_PRACTICE_LICK_KEY] = _lick(
            chart_key="C", chord="Dm7", concert_chord="Dm7",
            notes=["D", "F", "A", "C"], midi=[62, 65, 69, 72],
            concert_notes=["D", "F", "A", "C"], instrument="Piano",
        )
        self._start(ss)
        m = self._model(ss)
        self.assertEqual((m["current_label"], m["next_label"]), ("C major", "F major"))
        self.assertFalse(m["show_sounding"])
        kc.advance_key_cycle_now(ss)
        live = live_mission_model(ss, current_concert="F")
        self.assertEqual(live["chords_written"], ["Gm7"])
        self.assertEqual(live["motif"]["notes"], ["G", "Bb", "D", "F"])

    def test_missing_example_has_fallback_not_invented_notation(self) -> None:
        ss = self._session()
        self._start(ss)
        live = live_mission_model(ss, current_concert="C")
        self.assertTrue(live["fallback"])
        self.assertEqual(live["abc"], "")

    def test_not_shown_outside_mission_or_when_stopped(self) -> None:
        ss = self._session()
        self._start(ss)
        kc.stop_key_cycle(ss)
        self.assertIsNone(live_mission_model(ss, current_concert="C"))


class TestGuitarShapeMission(_MissionCycleCase):
    base = "G"

    def _guitar(self) -> dict:
        ss = self._session(instrument="Guitar", guitar_capo_enabled=True, guitar_capo_shape_key="E")
        # Shape key E (capo 3 sounds G). Written Am7 shape sounds Cm7 at capo 3.
        ss[MISSION_PRACTICE_LICK_KEY] = _lick(
            chart_key="E", chord="Am7", concert_chord="Cm7",
            notes=["A", "C", "E", "G"], midi=[57, 60, 64, 67],
            concert_notes=["C", "Eb", "G", "Bb"], instrument="Guitar",
        )
        return ss

    def test_shape_fixed_capo_and_sound_move(self) -> None:
        ss = self._guitar()
        self._start(ss)
        m = self._model(ss)
        self.assertEqual(m["mode"], "shape")
        self.assertEqual(m["shape_key_label"], "E major")
        self.assertEqual((m["capo"], m["next_capo"]), (3, 8))
        self.assertEqual(m["sounding_label"], "G major")
        first = live_mission_model(ss, current_concert="G")
        self.assertEqual(first["chords_written"], ["Am7"])
        self.assertEqual(first["chords_sounding"], ["Cm7"])
        kc.advance_key_cycle_now(ss)  # G -> C (+5): capo 8
        m = self._model(ss)
        self.assertEqual(m["capo"], 8)
        self.assertEqual(m["shape_key_label"], "E major")
        live = live_mission_model(ss, current_concert=kc.temporary_playback_key(ss))
        self.assertEqual(live["chords_written"], ["Am7"])
        self.assertEqual(live["motif"]["notes"], first["motif"]["notes"])
        self.assertEqual(live["abc"], first["abc"])
        self.assertEqual(live["chords_sounding"], ["Fm7"])

    def test_capo_stays_in_range_and_flags_the_wrap(self) -> None:
        ss = self._guitar()
        self._start(ss)
        frets = []
        wraps = 0
        for _ in range(12):
            m = self._model(ss)
            frets.append(m["capo"])
            wraps += int(m["capo_wraps"])
            self.assertLessEqual(m["next_capo"], 11)
            kc.advance_key_cycle_now(ss)
        self.assertEqual(sorted(frets), list(range(12)))
        self.assertGreater(wraps, 0)


class TestSpellingIsNotation(_MissionCycleCase):
    base = "C"

    def test_preference_relabels_without_moving(self) -> None:
        ss = self._session()
        self._start(ss)
        for _ in range(6):
            kc.advance_key_cycle_now(ss)  # C F Bb Eb Ab Db F#
        before = kc.get_owner_cycle_session(ss)
        self.assertEqual(self._model(ss)["current_label"], "F# major")
        ss[kc.BACKING_KEY_SPELLING_PREFS_KEY] = dict(kc.default_spelling_prefs(), **{"F#/Gb": "Gb"})
        m = self._model(ss)
        self.assertEqual(m["current_label"], "Gb major")
        after = kc.get_owner_cycle_session(ss)
        self.assertEqual(after["current_playback_key"], before["current_playback_key"])
        self.assertEqual(after["offset_semitones"], before["offset_semitones"])

    def test_every_default_and_override_pair(self) -> None:
        ss = self._session()
        self._start(ss, interval=1)
        for pair, default in kc.default_spelling_prefs().items():
            for choice in pair.split("/"):
                ss[kc.BACKING_KEY_SPELLING_PREFS_KEY] = dict(kc.default_spelling_prefs(), **{pair: choice})
                labels = self._model(ss)["labels"]
                tonics = {lab.split()[0] for lab in labels}
                self.assertIn(choice, tonics, (pair, choice, labels))
                other = [x for x in pair.split("/") if x != choice][0]
                self.assertNotIn(other, tonics, (pair, choice, labels))


class TestExerciseType(unittest.TestCase):
    def test_labels(self) -> None:
        self.assertEqual(exercise_type_for_mission("Target only guide tones (3rds & 7ths)"), "Guide Tones")
        self.assertEqual(exercise_type_for_mission("Focus on rhythm over note choice"), "Rhythm Study")
        self.assertEqual(exercise_type_for_mission("Something new"), "")


if __name__ == "__main__":
    unittest.main()
