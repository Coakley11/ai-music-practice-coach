"""The Blues groove bass sounds the chord the Lead Sheet shows, not the next one.

Reported 2026-11-11 on the user's Custom "Blues in F minor" (110 BPM, 4/4): the backing felt half a measure away from
the highlighted chord. Measured: the comping changed with the sheet, but the bass played the chord's 4th on beat 3 of
every bar (``flat7 = fifth - 2``), which in a blues is the root of the chord a 4th up -- the next chord -- so the bass
announced every change half a bar early. These render the user's exact chart through the real synth and look at every
bass note against the chord sounding at its onset.
"""
from __future__ import annotations

import unittest

import backing_audio as ba
from backing_musical_profile import resolve_backing_musical_profile_from_session
from song_coach_harmony import chord_facts

USER_CHART = ["Fm6", "Fm6", "Db7", "C7", "Fm6", "Fm6", "Db7|G7", "C7|Bbm7", "Fm7", "Bb7", "Fm7", "C7"]
BPM = 110.0


def _bass_notes(chords, *, style="Blues groove", bpm=BPM, loops=1):
    events = [{"chord": c, "section": "Verse", "bar_in_section": i, "section_bars": len(chords)} for i, c in enumerate(chords)]
    captured = []
    orig = ba._add_tone

    def spy(audio, sr, start, dur, midi, vol, wave_type="sine"):
        if wave_type in ("bass", "bass_upright"):
            captured.append((float(start), int(midi)))
        return orig(audio, sr, start, dur, midi, vol, wave_type)

    prof = resolve_backing_musical_profile_from_session({}, style=style, tempo=bpm, key="Fm")
    ba._add_tone = spy
    try:
        ba.synthesize_chords_to_numpy(events, bpm=bpm, loops=loops, style=style, song_title="Blues in F minor",
                                      musical_profile=prof, strings=False)
    finally:
        ba._add_tone = orig
    return sorted(captured)


def _chord_at(chords, beat):
    """(sounding chord, next chord) at ``beat`` of the form (two equal halves in a split bar), looping."""
    beat += 0.1  # onsets are humanized a few ms early: a note on a change belongs to the chord it starts
    bar = int(beat // 4) % len(chords)
    pos = beat % 4
    tok = chords[bar].split("|")
    cur = tok[0] if (len(tok) == 1 or pos < 2) else tok[1]
    nxt_bar = chords[(bar + 1) % len(chords)].split("|")[0]
    nxt = tok[1] if (len(tok) == 2 and pos < 2) else nxt_bar
    return cur, nxt


def _pcs(sym):
    f = chord_facts(sym)
    return {t.pc % 12 for t in f.tones} | {f.root_pc % 12}


class BluesBassChordToneTests(unittest.TestCase):
    def test_beat_three_is_a_tone_of_the_chord_being_shown(self) -> None:
        spb = 60.0 / BPM
        checked = 0
        for t, midi in _bass_notes(USER_CHART):
            beat = t / spb
            if abs((beat % 4) - 2.0) > 0.1:  # beat 3 (0-based 2.0), where the 4th used to sound
                continue
            cur, _nxt = _chord_at(USER_CHART, beat)
            self.assertIn(midi % 12, _pcs(cur), f"beat 3 of bar {int(beat // 4) + 1}: pc {midi % 12} under {cur}")
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_no_bass_note_announces_the_next_chord_early(self) -> None:
        """Away from the last beat (where a half-step approach belongs) every note is a tone of the current chord."""
        spb = 60.0 / BPM
        early = []
        for t, midi in _bass_notes(USER_CHART):
            beat = t / spb
            pos = beat % 4
            if pos >= 2.95 or pos < 0.05 or abs(pos - 2.0) < 0.05 and "|" in USER_CHART[int(beat // 4) % 12]:
                continue  # last beat (approach), the downbeat's humanized edge, a split bar's second chord
            cur, nxt = _chord_at(USER_CHART, beat)
            pc = midi % 12
            if pc not in _pcs(cur):
                early.append((round(beat + 1, 2), cur, nxt, pc))
        self.assertEqual(early, [], "bass notes that are not tones of the chord being shown")

    def test_the_seventh_comes_from_the_chord(self) -> None:
        names = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
        want = {"Fm6": "D", "Db7": "B", "C7": "Bb", "Fm7": "Eb", "Bb7": "Ab", "Bbm7": "Ab", "G7": "F",
                "Cmaj7": "B", "Bdim7": "Ab", "C": "Bb", "Fm": "Eb"}
        for chord, note in want.items():
            self.assertEqual(names[ba._bass_motion_pitch(chord, None, "Blues groove", 2, 7) % 12], note, chord)

    def test_other_grooves_are_untouched(self) -> None:
        # Jazz swing / Rock / Pop / Ballad build their own lines; only the Blues line changed.
        self.assertEqual(ba._bass_motion_pitch("C7", None, "Rock groove", 2, 8) % 12, 7)
        self.assertEqual(ba._bass_motion_pitch("C7", None, "Pop groove", 1, 2) % 12, 7)


if __name__ == "__main__":
    unittest.main()
