"""Perfect (Ed Sheeran) - compound-meter timing and complete form.

Two separate things were wrong here, and each gets its own class.

1. The stored tempo was in the WRONG UNIT. The engine's compound-meter grid
   (songs.meter.meter_timing) reads default_bpm as the *dotted-quarter pulse*
   rate: bar_sec = (num // 3) * 60 / bpm. Perfect stored 95, which is this
   song's *quarter-note* rate (Wikipedia's "190 BPM in 12/8" is the eighth-note
   rate; 190/2 = 95 quarters, 190/3 = 63.3 dotted quarters). Published editions
   mark dotted quarter = 63. Reading 95 as a dotted quarter played the song
   exactly 1.5x too fast.

2. Beginner and Intermediate DROPPED whole sections - Beginner lost Verse 3,
   Verse 4 and Chorus 3, i.e. 62 of 102 bars. Simpler harmony must not mean a
   shorter song.

The verse/chorus harmonic rhythm (verse: two bars per chord, chorus: one each)
was already correct and is pinned here so it cannot be flattened later.
"""

import pytest

from backing_audio import chord_notes
from chart_level_arrangement import resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from song_catalog.catalog import curated_song_records
from music_theory import transpose_sections_dict
from songs.chart_provenance import chart_fingerprint, versions_fingerprint
from songs.meter import meter_timing, metronome_accents

# Published reference: dotted quarter = 63 in 12/8 (Musicnotes editions; also
# Wikipedia's 63.33). One of their 12/8 bars is two of our 6/8 bars.
PUBLISHED_DOTTED_QUARTER = 63.0
PUBLISHED_EIGHTH_PER_MIN = PUBLISHED_DOTTED_QUARTER * 3
PUBLISHED_6_8_BAR_SEC = 6 * 60.0 / PUBLISHED_EIGHTH_PER_MIN  # 1.9048 s

SECTIONS = (
    "Intro", "Verse 1", "Verse 2", "Chorus 1",
    "Verse 3", "Verse 4", "Chorus 2", "Chorus 3", "Outro",
)


@pytest.fixture(scope="module")
def perfect():
    for rec in curated_song_records():
        if (rec.get("title") or "") == "Perfect":
            return rec
    pytest.fail("Perfect is not in the curated catalog")


def _runs(cells):
    """Lengths of consecutive runs of the same chord, in bars."""
    runs = []
    for cell in cells:
        if runs and runs[-1][0] == cell:
            runs[-1][1] += 1
        else:
            runs.append([cell, 1])
    return [n for _chord, n in runs]


class TestTheTempoIsADottedQuarterPulse:
    def test_the_bar_lasts_what_the_published_tempo_says(self, perfect):
        ext = perfect["extensions"]
        timing = meter_timing(ext["default_bpm"], ext["time_signature"])
        assert timing.bar_sec == pytest.approx(PUBLISHED_6_8_BAR_SEC, abs=1e-4)

    def test_the_old_quarter_note_rate_is_not_restored(self, perfect):
        """95 read as a dotted quarter gives a 1.2632 s bar - 1.5x too fast.

        95 is exactly 1.5x Wikipedia's precise 63.33; the stored 63 is the
        published rounded marking, so the measured ratio is 95/63 = 1.508.
        That 0.5% is the rounding, not a second error.
        """
        ext = perfect["extensions"]
        assert ext["default_bpm"] != 95
        stored = meter_timing(ext["default_bpm"], ext["time_signature"]).bar_sec
        wrong = meter_timing(95, ext["time_signature"]).bar_sec
        assert stored / wrong == pytest.approx(1.5, rel=0.01)
        assert stored > wrong
        # Why the factor is exactly 3/2: a 6/8 bar is 3 quarter notes but only
        # 2 dotted-quarter pulses. Reading a quarter-note rate as a pulse rate
        # therefore always shortens the bar by 2/3, whatever the number is.
        quarters_per_bar = 3 * 60.0 / 95.0  # 95 as the quarter rate -> 1.8947 s
        # within the 63-vs-63.333 rounding (0.53%)
        assert quarters_per_bar == pytest.approx(PUBLISHED_6_8_BAR_SEC, rel=0.01)
        assert quarters_per_bar / wrong == pytest.approx(1.5, abs=1e-9)

    def test_the_meter_stays_compound(self, perfect):
        ext = perfect["extensions"]
        timing = meter_timing(ext["default_bpm"], ext["time_signature"])
        assert timing.compound is True
        assert timing.pulses_per_bar == 6

    def test_two_dotted_quarter_pulses_per_bar(self, perfect):
        """ONE-two-three FOUR-five-six: strong clicks on eighths 1 and 4."""
        assert metronome_accents(perfect["extensions"]["time_signature"]) == [1, 4]

    def test_each_eighth_is_a_third_of_a_pulse(self, perfect):
        ext = perfect["extensions"]
        timing = meter_timing(ext["default_bpm"], ext["time_signature"])
        pulse = timing.bar_sec / 2.0
        assert timing.pulse_sec == pytest.approx(pulse / 3.0, abs=1e-6)

    def test_the_whole_chart_now_lasts_about_three_and_a_quarter_minutes(self, perfect):
        ext = perfect["extensions"]
        bar = meter_timing(ext["default_bpm"], ext["time_signature"]).bar_sec
        total = sum(len(v) for v in perfect["sections"].values()) * bar
        assert total == pytest.approx(194.3, abs=1.0)


class TestEveryLevelPlaysTheWholeSong:
    def test_no_level_drops_a_section(self, perfect, subtests):
        for level in ("Beginner", "Intermediate", "Advanced"):
            with subtests.test(level=level):
                _v, secs = resolve_level_chart(perfect, level)
                missing = [n for n in perfect["section_order"] if n not in secs]
                assert missing == []

    def test_every_level_is_the_full_bar_count(self, perfect, subtests):
        full = sum(len(v) for v in perfect["sections"].values())
        assert full == 102
        for level in ("Beginner", "Intermediate", "Advanced"):
            with subtests.test(level=level):
                _v, secs = resolve_level_chart(perfect, level)
                assert sum(len(v) for v in secs.values()) == full

    def test_the_final_chorus_and_both_later_sections_survive_at_beginner(self, perfect):
        _v, secs = resolve_level_chart(perfect, "Beginner")
        assert "Chorus 3" in secs
        assert "Verse 3" in secs
        assert "Verse 4" in secs

    def test_the_section_order_is_intact(self, perfect):
        assert tuple(perfect["section_order"]) == SECTIONS


class TestTheVerseChorusHarmonicRhythm:
    """Verse chords hold two 6/8 bars; chorus chords get one bar each."""

    def test_verse_chords_last_two_bars(self, perfect, subtests):
        for name in ("Verse 1", "Verse 2", "Verse 3", "Verse 4"):
            with subtests.test(section=name):
                assert set(_runs(perfect["sections"][name])) == {2}

    def test_chorus_chords_last_one_bar(self, perfect, subtests):
        for name in ("Chorus 1", "Chorus 2", "Chorus 3"):
            with subtests.test(section=name):
                assert set(_runs(perfect["sections"][name])) == {1}

    def test_a_verse_chord_lasts_one_published_twelve_eight_bar(self, perfect):
        ext = perfect["extensions"]
        bar = meter_timing(ext["default_bpm"], ext["time_signature"]).bar_sec
        twelve_eight_bar = 2 * PUBLISHED_6_8_BAR_SEC
        assert 2 * bar == pytest.approx(twelve_eight_bar, abs=1e-4)
        assert 1 * bar == pytest.approx(twelve_eight_bar / 2.0, abs=1e-4)

    def test_the_rhythm_holds_at_every_level(self, perfect, subtests):
        for level in ("Beginner", "Intermediate", "Advanced"):
            _v, secs = resolve_level_chart(perfect, level)
            for name in ("Verse 1", "Chorus 1"):
                with subtests.test(level=level, section=name):
                    expected = {2} if name.startswith("Verse") else {1}
                    assert set(_runs(secs[name])) == expected


class TestTheChartItselfIsUnchanged:
    """The TIMING fix was metadata only - it changed no chord and no level.

    A LATER, separate commit corrected the stored key from the capo-1 G shapes
    to the sounding concert Ab, and recorded the old fingerprint pair in
    songs/chart_revision_table.py. The timing-only property is therefore now
    checked by undoing that transposition: transpose the chart back to G and
    the fingerprints are exactly what the catalog had before either commit.
    See tests/test_perfect_concert_key.py for the key correction itself.
    """

    def test_fingerprints_are_the_known_values(self, perfect):
        """Current (concert Ab) pair, and the pre-correction G pair underneath."""
        assert chart_fingerprint(perfect["sections"]) == "774fdeb538765764"
        assert versions_fingerprint(perfect["chart_versions"]) == "0c8e530dd9ad3a0f"
        # Undo the key change: the timing fix itself altered no chord data.
        back = transpose_sections_dict(perfect["sections"], "Ab", "G")
        assert chart_fingerprint(back) == "a921e188a5039794"
        back_versions = {lvl: transpose_sections_dict(secs, "Ab", "G")
                         for lvl, secs in perfect["chart_versions"].items()}
        assert versions_fingerprint(back_versions) == "52577a3c2ddfbda9"

    def test_the_stored_key_is_concert_ab(self, perfect):
        """Was G - but those were capo-1 SHAPES, not sounding chords.

        Renamed from test_the_stored_key_is_untouched, which asserted G while
        the concert-key correction was still only a proposal.
        """
        assert perfect["key"] == "Ab"

    def test_chord_events_validate(self, perfect):
        ext = perfect["extensions"]
        events = sections_dict_to_events(
            perfect["sections"],
            time_signature=ext["time_signature"],
            section_order=perfect["section_order"],
        )
        assert len(events) == 102
        assert validate_chord_events(events, time_signature=ext["time_signature"]) == []

    def test_every_chord_symbol_voices(self, perfect, subtests):
        for level, secs in perfect["chart_versions"].items():
            symbols = {c for cells in secs.values() for c in cells}
            for sym in sorted(symbols):
                with subtests.test(level=level, chord=sym):
                    assert chord_notes(sym), sym


class TestTheGrooveIsGenuinelyCompound:
    """The 6/8 Ballad pattern must be two dotted-quarter pulses, not a 4/4
    backbeat wearing a 6/8 label."""

    @pytest.fixture(scope="class")
    def pattern(self):
        from backing_audio import _style_patterns

        return _style_patterns("Ballad", None, time_signature="6/8")

    def test_bass_lands_on_both_main_pulses(self, pattern):
        assert pattern["bass_beats"] == [0, 3]

    def test_the_kick_marks_the_bar_and_the_snare_the_second_pulse(self, pattern):
        assert pattern["kick_beats"] == [0]
        assert pattern["snare_beats"] == [3]

    def test_the_hats_divide_each_pulse_into_three(self, pattern):
        assert pattern["hat_beats"] == [0, 1, 2, 3, 4, 5]

    def test_nothing_lands_off_the_six_eighth_grid(self, pattern, subtests):
        for key in ("bass_beats", "comp_beats", "hat_beats", "snare_beats", "kick_beats"):
            with subtests.test(pattern_key=key):
                assert all(0 <= beat < 6 for beat in pattern[key])
