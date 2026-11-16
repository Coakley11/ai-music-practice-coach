"""Kiss Me - Sixpence None the Richer: the verified form, key, tempo and chorus.

What the sources actually establish, and what they do not:

* **Key Eb major** - the Musicnotes piano/vocal/chords edition states Eb major as
  the original published key, in 4/4, and Wikipedia's infobox repeats it.  The
  chart is *stored* in open D shapes (how every tab site prints it, capo 1) and
  transposed up a semitone at build time, so the two must never be confused.
* **100 BPM** - the better of the two candidate tempos.  88 bars at 100 BPM is
  3:31 against a 3:30 album version; the published score's ``q = 96`` marking
  would run 3:40.  Three audio-analysis sources report 99.9-100.
* **The 88-bar form** - confirmed by that duration agreement, and the 9-bar
  chorus matches the bellandcomusic.com bar-formatted chart slot for slot,
  including the single whole-bar IV and the shared sus4/triad last bar.
* **Two chorus chords are NOT settled** (bars 6-7).  Four sources agree the
  bar-7 bass is Bb and disagree about the chord above it.  The tests below pin
  what every source agrees on and deliberately leave those two slots free.

The defect this file guards is the level trim: Beginner used to lose "Chorus 3"
(the final chorus) and "Harmonica / Accordion", and Intermediate lost
"Chorus 3", so neither level ever reached the last chorus.
"""

from __future__ import annotations

import pytest

from backing_audio import chord_notes
from chart_level_arrangement import keeps_full_form, resolve_level_chart
from music_theory import transpose_sections_dict
from song_catalog.catalog import curated_song_records
from songs.chart_provenance import chart_fingerprint, versions_fingerprint
from songs.meter import meter_timing

LEVELS = ("Beginner", "Intermediate", "Advanced")

# Pinned so a chart edit has to be deliberate - these are also the values a
# saved chart carries, so changing them would re-stamp every stored revision.
SECTIONS_FP = "0b247fe413daa621"
VERSIONS_FP = "e5578a971ab7e1ba"

ALBUM_SECONDS = 210.0  # 3:30, Wikipedia infobox
TOTAL_BARS = 88

EB_MAJOR_SCALE = {"Eb", "F", "G", "Ab", "Bb", "C", "D"}
D_PITCH_CLASS = 2  # the leading tone of Eb, i.e. the 3rd of the V chord


@pytest.fixture(scope="module")
def kiss():
    for rec in curated_song_records():
        if (rec.get("title") or "").strip().lower() == "kiss me":
            return rec
    raise AssertionError("Kiss Me is not in the catalog")


def _cells(sections):
    return sum(len(v) for v in sections.values())


def _root(symbol):
    head = symbol[:-3] if symbol.endswith("6/9") else symbol.split("/")[0]
    return head[:2] if len(head) > 1 and head[1] in "b#" else head[:1]


def _pitches(symbol):
    """Sounding pitch classes, slash bass included."""
    out = {n % 12 for n in chord_notes(symbol)}
    parts = symbol.split("/")
    if len(parts) == 2 and len(parts[1]) <= 2:
        out |= {chord_notes(parts[1])[0] % 12}
    return out


class TestTheSoundingKeyIsEbNotTheGuitarShape:
    def test_the_stored_key_is_concert_eb(self, kiss):
        assert kiss["key"] == "Eb"
        assert kiss["extensions"]["concert_key"] == "Eb"

    def test_the_shape_set_is_recorded_separately_as_d(self, kiss):
        """The chart is printed in D shapes with a capo; that is not the key."""
        ext = kiss["extensions"]
        assert ext["guitar_friendly_key"] == "D"
        assert "capo 1" in ext["capo_note"].lower()
        assert "eb major" in ext["capo_note"].lower()

    def test_every_chord_is_diatonic_to_eb_or_a_documented_colour(self, kiss):
        """No chord has a root outside Eb major, at any level."""
        for level, sections in kiss["chart_versions"].items():
            for name, cells in sections.items():
                for cell in cells:
                    for part in cell.split("|"):
                        assert _root(part) in EB_MAJOR_SCALE, (level, name, part)

    def test_no_chord_is_spelled_with_a_sharp(self, kiss):
        """Eb major is a flat key; a sharp would mean a stale transposition."""
        for level, sections in kiss["chart_versions"].items():
            for name, cells in sections.items():
                for cell in cells:
                    assert "#" not in cell, (level, name, cell)

    def test_transposing_back_to_d_reproduces_the_printed_shapes(self, kiss):
        """Concert Eb -> D must give the open shapes the tab sites print."""
        shapes = transpose_sections_dict(kiss["sections"], "Eb", "D")
        assert shapes["Intro"] == ["D", "Dmaj7", "D7", "Dmaj7"] * 2
        assert shapes["Verse 1"] == [
            "D", "Dmaj7", "D7", "Dmaj7", "D", "Dmaj7", "D7", "G",
        ]
        assert shapes["Guitar Section"] == ["Em|A", "D|Bm", "Em|A", "D|D7"]


class TestTheTempoAndFormMatchTheRecord:
    def test_the_tempo_is_one_hundred_in_four_four(self, kiss):
        ext = kiss["extensions"]
        assert ext["default_bpm"] == 100
        assert ext["time_signature"] == "4/4"

    def test_four_four_is_not_read_as_a_compound_meter(self, kiss):
        """100 is the quarter-note rate here - the Perfect trap, ruled out."""
        timing = meter_timing(kiss["extensions"]["default_bpm"],
                              kiss["extensions"]["time_signature"])
        assert timing.compound is False
        assert timing.bar_sec == pytest.approx(2.4)

    def test_the_stored_form_plays_within_two_seconds_of_the_album_version(self, kiss):
        timing = meter_timing(100, "4/4")
        played = _cells(kiss["sections"]) * timing.bar_sec
        assert _cells(kiss["sections"]) == TOTAL_BARS
        assert played == pytest.approx(211.2)
        assert abs(played - ALBUM_SECONDS) < 2.0

    def test_the_published_scores_ninety_six_would_run_ten_seconds_long(self):
        """Why 100 is stored rather than the score's q=96 marking."""
        slow = TOTAL_BARS * meter_timing(96, "4/4").bar_sec
        assert slow == pytest.approx(220.0)
        assert slow - ALBUM_SECONDS > 9.0

    def test_the_section_order_is_the_published_form(self, kiss):
        assert kiss["section_order"] == [
            "Intro", "Verse 1", "Chorus 1", "Interlude", "Verse 2", "Chorus 2",
            "Harmonica / Accordion", "Guitar Section", "Chorus 3", "Outro",
        ]


class TestEveryLevelReachesTheFinalChorus:
    """The defect: the generic trim dropped Chorus 3 at Beginner AND Intermediate."""

    def test_all_three_levels_keep_the_whole_form(self, kiss):
        for level in LEVELS:
            assert keeps_full_form(kiss, level) is True, level

    def test_full_form_levels_survived_the_core_ref_whitelist(self, kiss):
        """core_ref copies only named fields into extensions - this is one."""
        assert kiss["extensions"]["full_form_levels"] == ["Beginner", "Intermediate"]

    def test_no_level_is_missing_a_section(self, kiss):
        for level in LEVELS:
            _view, sections = resolve_level_chart(kiss, level)
            missing = [n for n in kiss["section_order"] if n not in sections]
            assert missing == [], (level, missing)

    def test_the_final_chorus_and_the_harmonica_break_play_at_every_level(self, kiss):
        for level in LEVELS:
            _view, sections = resolve_level_chart(kiss, level)
            assert "Chorus 3" in sections, level
            assert "Harmonica / Accordion" in sections, level

    def test_every_level_plays_the_same_eighty_eight_bars(self, kiss):
        for level in LEVELS:
            _view, sections = resolve_level_chart(kiss, level)
            assert _cells(sections) == TOTAL_BARS, level

    def test_the_bar_grid_is_identical_across_levels(self, kiss):
        """Levels change chords, never timing, so backing stays in sync."""
        shape = {n: len(c) for n, c in kiss["sections"].items()}
        for level in LEVELS:
            _view, sections = resolve_level_chart(kiss, level)
            assert {n: len(c) for n, c in sections.items()} == shape, level


class TestTheChorusMatchesTheBarFormattedReference:
    def test_the_chorus_is_nine_bars(self, kiss):
        for name in ("Chorus 1", "Chorus 2", "Chorus 3"):
            assert len(kiss["sections"][name]) == 9, name

    def test_the_three_choruses_are_the_same_chart(self, kiss):
        first = kiss["sections"]["Chorus 1"]
        assert kiss["sections"]["Chorus 2"] == first
        assert kiss["sections"]["Chorus 3"] == first

    def test_the_fourth_bar_is_the_only_whole_bar_chord(self, kiss):
        """The reference prints one whole-bar chord in the chorus: the IV."""
        whole = [c for c in kiss["sections"]["Chorus 1"] if "|" not in c]
        assert whole == ["Abmaj7"]

    def test_the_slots_every_source_agrees_on(self, kiss):
        """Bars 1-5 and 8-9, which all four consulted sources share."""
        chorus = kiss["sections"]["Chorus 1"]
        assert chorus[0] == "Fm|Bb"
        assert chorus[2] == "Fm|Bb"
        assert chorus[3] == "Eb|Eb7"
        assert chorus[4] == "Fm|Bb"
        assert chorus[7] == "Abmaj7"
        assert chorus[8] == "Bbsus4|Bb"

    def test_the_bar_seven_bass_is_bb_whichever_reading_wins(self, kiss):
        """The one thing all four sources agree on in the open passage."""
        second_half = kiss["sections"]["Chorus 1"][6].split("|")[1]
        assert second_half.endswith("/Bb")

    def test_our_cm7_is_the_same_chord_as_the_sources_slash_spelling(self, kiss):
        """D/B at capo 1 is Eb/C, which IS Cm7 - a spelling, not a difference."""
        assert _pitches("Eb/C") == _pitches("Cm7")
        assert kiss["sections"]["Chorus 1"][6].split("|")[0] == "Cm7"

    def test_the_guitar_section_is_the_chorus_opening_in_four_bars(self, kiss):
        assert kiss["sections"]["Guitar Section"] == kiss["sections"]["Chorus 1"][:4]

    def test_the_intro_cycle_is_the_songs_signature_chromatic_line(self, kiss):
        """Eb - D - Db - D in an inner voice; the hook of the arrangement."""
        cycle = ["Eb", "Ebmaj7", "Eb7", "Ebmaj7"]
        assert kiss["sections"]["Intro"] == cycle * 2
        assert kiss["sections"]["Interlude"] == cycle * 2
        assert kiss["sections"]["Harmonica / Accordion"] == cycle * 2

    def test_the_verse_ends_on_the_subdominant(self, kiss):
        assert kiss["sections"]["Verse 1"][-1] == "Ab"
        assert kiss["sections"]["Verse 1"] == kiss["sections"]["Verse 2"]


class TestTheLevelChartsKeepTheUnderlyingHarmony:
    def test_no_level_changes_a_chord_root(self, kiss):
        """Simplify and embellish are allowed; re-harmonising is not."""
        base = kiss["sections"]
        for level, sections in kiss["chart_versions"].items():
            for name, cells in sections.items():
                for i, cell in enumerate(cells):
                    want = base[name][i].split("|")
                    got = cell.split("|")
                    assert len(got) == len(want), (level, name, i)
                    for a, b in zip(want, got):
                        assert _root(a) == _root(b), (level, name, i, a, b)

    def test_beginner_states_only_plain_triads_and_sevenths(self, kiss):
        """Beginner may drop colour, but every chord must stay playable."""
        for name, cells in kiss["chart_versions"]["Beginner"].items():
            for cell in cells:
                for part in cell.split("|"):
                    assert "add" not in part and "sus" not in part, (name, part)
                    assert "9" not in part and "/" not in part, (name, part)

    def test_advanced_extensions_contain_the_base_chord_or_add_to_it(self, kiss):
        """An Advanced voicing must not drop a note the base chord states,
        except where it deliberately substitutes a suspension."""
        base = kiss["sections"]
        allowed_suspensions = {"Bbsus2", "Bb7sus4"}
        for name, cells in kiss["chart_versions"]["Advanced"].items():
            for i, cell in enumerate(cells):
                for a, b in zip(base[name][i].split("|"), cell.split("|")):
                    if b in allowed_suspensions:
                        continue
                    assert _pitches(a) <= _pitches(b), (name, i, a, b)

    def test_the_advanced_dominant_is_the_one_substitution_in_the_chart(self, kiss):
        """Recorded, not endorsed: Advanced plays the V as sus2/7sus4, so the
        chorus never states the leading tone D.  Flagged for review - if this
        is changed, this test is the place that says it was a choice."""
        advanced_chorus = kiss["chart_versions"]["Advanced"]["Chorus 1"]
        dominants = {p for cell in advanced_chorus for p in cell.split("|")
                     if _root(p) == "Bb"}
        assert dominants == {"Bbsus2", "Bb7sus4"}
        for symbol in dominants:
            assert D_PITCH_CLASS not in _pitches(symbol), symbol
        assert D_PITCH_CLASS in _pitches("Bb")  # the base chart does state it


class TestSavedChartsAreUntouched:
    def test_the_fingerprints_did_not_move(self, kiss):
        """Enabling full_form_levels must not re-stamp a single saved chart."""
        assert chart_fingerprint(kiss["sections"]) == SECTIONS_FP
        assert versions_fingerprint(kiss["chart_versions"]) == VERSIONS_FP

    def test_full_form_levels_lives_outside_the_chart(self, kiss):
        """It is extensions metadata, so it cannot change a chart fingerprint."""
        assert "full_form_levels" in kiss["extensions"]
        assert "full_form_levels" not in kiss["sections"]
