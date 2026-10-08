"""Tests for the Practice Melody generation engine (practice_melody_generator.py).

Covers: song-specific generation, level differentiation, musical coherence
(strong beats / phrase endings land on chord tones), rhythm/form validity,
deterministic regeneration, and deliberate repeat-section handling. These
exercise the generator against several materially different progressions
(major/minor, different forms and tempos) rather than a single fixture, per
the Slice A brief.
"""

from __future__ import annotations

import unittest

from practice_melody_generator import generate_another_practice_melody, generate_practice_melody
from practice_melody_model import validate_practice_melody, VALID_LEVELS

# Representative, materially different progressions/forms/keys/tempos/styles.
# Deliberately NOT sourced from any real song's melody -- only chord symbols,
# which the generator treats as harmonic context, are used anywhere here.
_SONGS: dict[str, dict] = {
    "pop-major-ballad": {
        "song_title": "Acoustic Pop Ballad (test fixture)",
        "sections": {
            "Intro": ["G", "D/F#", "Em7", "D", "Cadd9", "D", "G", "G"],
            "Verse 1": (["G", "Em7", "Cadd9", "D/F#"] * 2),
            "Chorus": ["Em7", "Cadd9", "G", "D/F#", "Em7", "Cadd9", "G", "D/F#"],
            "Verse 2": (["G", "Em7", "Cadd9", "D/F#"] * 2),
        },
        "section_order": ["Intro", "Verse 1", "Chorus", "Verse 2"],
        "key_center": "G",
        "tempo_bpm": 76.0,
        "style": "Acoustic pop ballad",
    },
    "minor-key-rock": {
        "song_title": "Minor Key Rock Anthem (test fixture)",
        "sections": {
            "Verse 1": ["Am", "F", "C", "G"] * 4,
            "Chorus": ["F", "C", "G", "Am"] * 2,
            "Bridge": ["Dm", "G", "Em", "Am"],
        },
        "section_order": ["Verse 1", "Chorus", "Bridge"],
        "key_center": "Am",
        "tempo_bpm": 132.0,
        "style": "Rock",
    },
    "jazz-ii-v-i": {
        "song_title": "Jazz Standard Form (test fixture)",
        "sections": {
            "A": ["Dm7", "G7", "Cmaj7", "Cmaj7", "Dm7", "G7", "Cmaj7", "A7"],
            "B": ["Dm7", "G7", "Em7", "A7", "Dm7", "G7", "Cmaj7", "Cmaj7"],
        },
        "section_order": ["A", "B"],
        "key_center": "C",
        "tempo_bpm": 118.0,
        "style": "Jazz swing",
    },
}


def _generate_all_levels(song_key: str, **overrides) -> dict[str, object]:
    spec = dict(_SONGS[song_key])
    spec.update(overrides)
    out = {}
    for level in VALID_LEVELS:
        out[level] = generate_practice_melody(song_id=song_key, level=level, **spec)
    return out


class TestStructuralValidityAcrossSongsAndLevels(unittest.TestCase):
    def test_all_fixture_songs_all_levels_are_structurally_valid(self) -> None:
        for song_key in _SONGS:
            for level, melody in _generate_all_levels(song_key).items():
                problems = validate_practice_melody(melody)
                self.assertEqual(problems, [], f"{song_key}/{level}: {problems}")

    def test_other_meter_still_valid(self) -> None:
        melody = generate_practice_melody(
            song_id="waltz-fixture", song_title="Waltz (test fixture)",
            sections={"A": ["C", "G", "Am", "F"]}, key_center="C",
            level="Intermediate", meter=(3, 4),
        )
        self.assertEqual(validate_practice_melody(melody), [])
        for section in melody.sections:
            self.assertEqual(section.beats_per_measure, 3.0)


class TestSongSpecificity(unittest.TestCase):
    def test_chord_tone_events_match_their_actual_chord(self) -> None:
        """Every chord_tone event's pitch class must be a real chord tone of
        the chord sounding in that measure -- proof the generator is reading
        each song's own harmony rather than emitting interchangeable notes."""
        for song_key in _SONGS:
            melody = generate_practice_melody(song_id=song_key, level="Advanced", **_SONGS[song_key])
            for section in melody.sections:
                for event in section.events:
                    if event.is_rest or event.tone_role != "chord_tone":
                        continue
                    from practice_melody_generator import _chord_tone_pcs

                    allowed = _chord_tone_pcs(event.chord)
                    self.assertIn(
                        event.midi % 12, allowed,
                        f"{song_key}/{section.section_id} m{event.measure}: "
                        f"{event.pitch} not a chord tone of {event.chord}",
                    )

    def test_different_songs_produce_different_melodies(self) -> None:
        pop = generate_practice_melody(song_id="pop-major-ballad", level="Intermediate", **_SONGS["pop-major-ballad"])
        jazz = generate_practice_melody(song_id="jazz-ii-v-i", level="Intermediate", **_SONGS["jazz-ii-v-i"])
        self.assertNotEqual(
            [e.midi for s in pop.sections for e in s.events if not e.is_rest],
            [e.midi for s in jazz.sections for e in s.events if not e.is_rest],
        )


class TestLevelDifferentiation(unittest.TestCase):
    def _stats(self, melody) -> dict[str, float]:
        durations = set()
        roles: dict[str, int] = {}
        leaps = []
        prev_midi = None
        for section in melody.sections:
            for event in section.events:
                if event.is_rest:
                    continue
                durations.add(event.duration_beats)
                roles[event.tone_role] = roles.get(event.tone_role, 0) + 1
                if prev_midi is not None:
                    leaps.append(abs(event.midi - prev_midi))
                prev_midi = event.midi
        total = sum(roles.values()) or 1
        return {
            "distinct_durations": len(durations),
            "min_duration": min(durations) if durations else 4.0,
            "non_chord_tone_fraction": 1.0 - (roles.get("chord_tone", 0) / total),
            "avg_leap": (sum(leaps) / len(leaps)) if leaps else 0.0,
        }

    def test_beginner_is_simpler_than_advanced_for_every_fixture_song(self) -> None:
        for song_key in _SONGS:
            levels = _generate_all_levels(song_key)
            beginner_stats = self._stats(levels["Beginner"])
            intermediate_stats = self._stats(levels["Intermediate"])
            advanced_stats = self._stats(levels["Advanced"])

            self.assertLessEqual(
                beginner_stats["non_chord_tone_fraction"],
                intermediate_stats["non_chord_tone_fraction"] + 1e-9,
                f"{song_key}: Beginner should use no more non-chord-tone motion than Intermediate",
            )
            self.assertLessEqual(
                intermediate_stats["non_chord_tone_fraction"],
                advanced_stats["non_chord_tone_fraction"] + 1e-9,
                f"{song_key}: Intermediate should use no more non-chord-tone motion than Advanced",
            )
            # Advanced's rhythm vocabulary must reach finer subdivisions
            # (sixteenth notes) that Beginner never uses.
            self.assertGreaterEqual(beginner_stats["min_duration"], 0.5)
            self.assertLessEqual(advanced_stats["min_duration"], 0.5)

    def test_beginner_never_uses_sixteenth_notes(self) -> None:
        for song_key in _SONGS:
            melody = generate_practice_melody(song_id=song_key, level="Beginner", **_SONGS[song_key])
            for section in melody.sections:
                for event in section.events:
                    self.assertGreaterEqual(event.duration_beats, 0.5, f"{song_key}: Beginner used a duration < eighth note")

    def test_beginner_leaps_stay_within_a_fifth(self) -> None:
        for song_key in _SONGS:
            melody = generate_practice_melody(song_id=song_key, level="Beginner", **_SONGS[song_key])
            prev_midi = None
            for section in melody.sections:
                for event in section.events:
                    if event.is_rest:
                        continue
                    if prev_midi is not None:
                        self.assertLessEqual(abs(event.midi - prev_midi), 7)
                    prev_midi = event.midi


class TestMusicalCoherence(unittest.TestCase):
    def test_downbeats_are_always_chord_tones(self) -> None:
        for song_key in _SONGS:
            for level in VALID_LEVELS:
                melody = generate_practice_melody(song_id=song_key, level=level, **_SONGS[song_key])
                for section in melody.sections:
                    for event in section.events:
                        if event.is_rest or event.beat != 0.0:
                            continue
                        self.assertEqual(
                            event.tone_role, "chord_tone",
                            f"{song_key}/{level}/{section.section_id} m{event.measure}: downbeat is {event.tone_role}",
                        )

    def test_section_final_note_resolves_to_chord_tone(self) -> None:
        for song_key in _SONGS:
            for level in VALID_LEVELS:
                melody = generate_practice_melody(song_id=song_key, level=level, **_SONGS[song_key])
                for section in melody.sections:
                    sounding = [e for e in section.events if not e.is_rest]
                    self.assertTrue(sounding)
                    last = sounding[-1]
                    self.assertEqual(last.tone_role, "chord_tone")
                    from practice_melody_generator import _chord_tone_pcs

                    root_and_third = _chord_tone_pcs(last.chord)[:2]
                    self.assertIn(last.midi % 12, root_and_third)


class TestRepeatSectionHandling(unittest.TestCase):
    def test_identical_chord_progression_repeats_the_same_melody(self) -> None:
        melody = generate_practice_melody(song_id="pop-major-ballad", level="Intermediate", **_SONGS["pop-major-ballad"])
        verse1 = melody.section_by_id("Verse 1")
        verse2 = melody.section_by_id("Verse 2")
        self.assertIsNotNone(verse1)
        self.assertIsNotNone(verse2)
        self.assertEqual(verse2.repeat_of, "Verse 1")
        self.assertEqual(
            [e.to_dict() for e in verse1.events],
            [e.to_dict() for e in verse2.events],
        )


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_same_seed_produce_identical_output(self) -> None:
        a = generate_practice_melody(song_id="jazz-ii-v-i", level="Advanced", seed=4242, **_SONGS["jazz-ii-v-i"])
        b = generate_practice_melody(song_id="jazz-ii-v-i", level="Advanced", seed=4242, **_SONGS["jazz-ii-v-i"])
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_same_inputs_no_explicit_seed_are_still_reproducible(self) -> None:
        """Without an explicit seed, the derived seed must be stable across
        runs so 'the same song at the same level' always calls back the
        same melody unless the caller explicitly asks for another one."""
        a = generate_practice_melody(song_id="jazz-ii-v-i", level="Advanced", **_SONGS["jazz-ii-v-i"])
        b = generate_practice_melody(song_id="jazz-ii-v-i", level="Advanced", **_SONGS["jazz-ii-v-i"])
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_generate_another_changes_seed_and_output_but_keeps_song_and_level(self) -> None:
        first = generate_practice_melody(song_id="minor-key-rock", level="Advanced", **_SONGS["minor-key-rock"])
        second = generate_another_practice_melody(first)
        third = generate_another_practice_melody(second)

        self.assertNotEqual(first.seed, second.seed)
        self.assertNotEqual(second.seed, third.seed)
        self.assertEqual(second.alt_index, first.alt_index + 1)
        self.assertEqual(third.alt_index, first.alt_index + 2)
        self.assertEqual(second.song_id, first.song_id)
        self.assertEqual(second.level, first.level)
        self.assertNotEqual(
            [e.midi for s in first.sections for e in s.events if not e.is_rest],
            [e.midi for s in second.sections for e in s.events if not e.is_rest],
        )

    def test_generate_another_is_itself_reproducible(self) -> None:
        first = generate_practice_melody(song_id="minor-key-rock", level="Advanced", **_SONGS["minor-key-rock"])
        second_a = generate_another_practice_melody(first)
        # Recreate "first" identically, then ask for its next alternative again.
        first_again = generate_practice_melody(song_id="minor-key-rock", level="Advanced", **_SONGS["minor-key-rock"])
        second_b = generate_another_practice_melody(first_again)
        self.assertEqual(second_a.to_dict(), second_b.to_dict())

    def test_different_levels_of_same_song_do_not_collide_on_seed(self) -> None:
        beginner = generate_practice_melody(song_id="minor-key-rock", level="Beginner", **_SONGS["minor-key-rock"])
        advanced = generate_practice_melody(song_id="minor-key-rock", level="Advanced", **_SONGS["minor-key-rock"])
        self.assertNotEqual(beginner.seed, advanced.seed)


class TestMelodyIdentityAndSourceLabel(unittest.TestCase):
    def test_source_is_always_generated_for_this_engine(self) -> None:
        melody = generate_practice_melody(song_id="pop-major-ballad", level="Beginner", **_SONGS["pop-major-ballad"])
        self.assertEqual(melody.source, "generated")

    def test_melody_id_distinguishes_song_level_and_alt_index(self) -> None:
        a = generate_practice_melody(song_id="pop-major-ballad", level="Beginner", **_SONGS["pop-major-ballad"])
        b = generate_practice_melody(song_id="pop-major-ballad", level="Advanced", **_SONGS["pop-major-ballad"])
        c = generate_another_practice_melody(a)
        ids = {a.melody_id, b.melody_id, c.melody_id}
        self.assertEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
