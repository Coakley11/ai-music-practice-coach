"""Perfect (Ed Sheeran) - the chart stores CONCERT chords in Ab, not G shapes.

The catalog used to store **G, Em7, Cadd9, D/F#**, which are the shapes Sheeran
grips with a **capo on fret 1**. Read as sounding chords they put the whole song
a semitone below the record, so a flautist or saxophonist playing along with the
single was out by a semitone the whole way through. The chart now stores the
sounding chords (**Ab, Fm7, Dbadd9, Eb/G**).

Sources: Wikipedia ("written in the key of Ab major", though also "G major in
live performances"), a Musicnotes edition ("Original Published Key: Ab Major"),
a guitar lesson ("capo on fret 1, sounding in Ab major; chords are written in G
major") and a chart listing the concert chords as Ab/Fm7/Db/Eb.

Nothing in G is lost, and that is what most of this file proves:
  * Capo mode auto-selects shape key **G at fret 1** for Ab.
  * **Practice Key G reproduces the previous chart exactly**, at every level.
  * A saved G chart is still recognised as a prior catalog revision, while a
    genuinely user-edited chart is still left alone.

The timing correction from the previous commit (dotted quarter = 63, all three
levels playing 102 bars) must survive untouched; the last class checks that.
"""

import pytest

from backing_audio import bass_note, chord_notes
from chart_level_arrangement import keeps_full_form, resolve_level_chart
from chord_events import sections_dict_to_events, validate_chord_events
from guitar_capo import capo_fret_for_shape, default_shape_key_for_sounding
from instrument_transposition import (is_transposing_instrument,
                                      saxophone_display_names,
                                      saxophone_type_for_display_name,
                                      written_key_for_saxophone)
from music_theory import (conventional_key_options, display_key_options,
                          transpose_sections_dict)
from song_catalog.catalog import curated_song_records
from songs.chart_provenance import (CATALOG_REVISION_KEY, CHART_ORIGIN_KEY, KEEP,
                                    ORIGIN_CATALOG, REFRESH, chart_fingerprint,
                                    classify_snapshot, is_known_prior_revision,
                                    revision_key, versions_fingerprint)
from songs.chart_revision_table import PRIOR_REVISIONS
from songs.meter import meter_timing

# The chart as it was BEFORE this correction (G shapes stored as concert chords).
PRIOR_G_SECTIONS_FP = "a921e188a5039794"
PRIOR_G_VERSIONS_FP = "52577a3c2ddfbda9"
# The corrected concert-Ab chart.
AB_SECTIONS_FP = "774fdeb538765764"
AB_VERSIONS_FP = "0c8e530dd9ad3a0f"

CATALOG_PICK = "Pop\x1fPerfect – Ed Sheeran"
AB_MAJOR_SCALE = {"Ab", "Bb", "C", "Db", "Eb", "F", "G"}


@pytest.fixture(scope="module")
def perfect():
    for rec in curated_song_records():
        if (rec.get("title") or "") == "Perfect":
            return rec
    pytest.fail("Perfect is not in the curated catalog")


@pytest.fixture(scope="module")
def symbols(perfect):
    out = []
    for secs in perfect["chart_versions"].values():
        for cells in secs.values():
            for c in cells:
                if c not in out:
                    out.append(c)
    return out


def _root_of(symbol):
    """Chord root, allowing for a flat/sharp. '/9' in 6/9 is a quality, not a bass."""
    head = symbol[:-3] if symbol.endswith("6/9") else symbol.split("/")[0]
    return head[:2] if len(head) > 1 and head[1] in "b#" else head[:1]


class TestTheStoredKeyIsConcertAb:
    def test_the_catalog_key_is_ab(self, perfect):
        assert perfect["key"] == "Ab"

    def test_the_old_g_key_is_not_restored(self, perfect):
        assert perfect["key"] != "G"

    def test_every_chord_root_is_diatonic_to_ab_major(self, perfect, symbols, subtests):
        for sym in symbols:
            with subtests.test(chord=sym):
                assert _root_of(sym) in AB_MAJOR_SCALE

    def test_the_spelling_uses_flats_not_sharps(self, symbols, subtests):
        """Ab major is a flat key: a G# or D# here would be a spelling bug."""
        for sym in symbols:
            with subtests.test(chord=sym):
                assert "#" not in sym

    def test_the_tonic_and_the_four_core_chords_are_present(self, perfect):
        verse = perfect["sections"]["Verse 1"]
        assert sorted(set(verse)) == ["Ab", "Dbadd9", "Eb/G", "Fm7"]
        chorus = perfect["sections"]["Chorus 1"]
        assert sorted(set(chorus)) == ["Ab", "Dbadd9", "Eb/G", "Fm7"]


class TestNothingMusicalWasLostInTransposition:
    """The correction must be a pure transposition - not a re-harmonisation."""

    def test_the_chart_is_exactly_the_prior_chart_transposed_up_one_semitone(self, perfect):
        """Transposing back to G must reproduce the recorded prior revision.

        This is the strongest available check that the hand-written Ab symbols
        are right: the fingerprint it must hit is the one the revision table
        recorded from the pre-correction checkout.
        """
        back = transpose_sections_dict(perfect["sections"], "Ab", "G")
        assert chart_fingerprint(back) == PRIOR_G_SECTIONS_FP

    def test_every_level_round_trips_to_the_prior_revision(self, perfect):
        back = {lvl: transpose_sections_dict(secs, "Ab", "G")
                for lvl, secs in perfect["chart_versions"].items()}
        assert versions_fingerprint(back) == PRIOR_G_VERSIONS_FP

    def test_the_slash_bass_notes_survived(self, perfect, symbols):
        """D/F# -> Eb/G and Gmaj9/B -> Abmaj9/C: the bass stays the chord's third."""
        slashes = [s for s in symbols if "/" in s and not s.endswith("6/9")]
        assert sorted(slashes) == ["Abmaj9/C", "Eb/G"]
        # Eb/G: G is the major third of Eb. Abmaj9/C: C is the major third of Ab.
        assert bass_note("Eb/G") % 12 == 7       # G
        assert bass_note("Abmaj9/C") % 12 == 0   # C
        assert bass_note("Eb/G") != bass_note("Eb")

    def test_the_advanced_chord_qualities_survived(self, perfect):
        adv = perfect["chart_versions"]["Advanced"]
        present = {c for cells in adv.values() for c in cells}
        assert present == {"Ab6", "Abmaj9", "Abmaj9/C", "Db6/9", "Dbmaj9",
                           "Eb/G", "Eb13sus4", "Ebadd9", "Fm9"}

    def test_the_quality_of_each_chord_is_unchanged(self, perfect, subtests):
        """Strip the root from old and new: the quality suffix must be identical."""
        for lvl, secs in perfect["chart_versions"].items():
            back = transpose_sections_dict(secs, "Ab", "G")
            for name in secs:
                for new, old in zip(secs[name], back[name]):
                    with subtests.test(level=lvl, section=name, chord=new):
                        new_q = new[len(_root_of(new)):]
                        old_q = old[len(_root_of(old)):]
                        # Slash basses move with the chord, so compare only the
                        # quality that precedes a '/' (except the 6/9 quality).
                        if "/" in new_q and not new.endswith("6/9"):
                            new_q, old_q = new_q.split("/")[0], old_q.split("/")[0]
                        assert new_q == old_q

    def test_every_symbol_still_voices(self, symbols, subtests):
        for sym in symbols:
            with subtests.test(chord=sym):
                assert chord_notes(sym), sym

    def test_the_chord_count_per_section_is_unchanged(self, perfect):
        """A transposition may not add or drop a bar."""
        assert sum(len(v) for v in perfect["sections"].values()) == 102


class TestGuitaristsKeepTheirGShapes:
    def test_capo_mode_auto_selects_g_shapes_at_fret_one(self, perfect):
        """Ab is unplayable in open position; G + capo 1 is the real-world answer."""
        shape = default_shape_key_for_sounding(perfect["key"])
        assert shape == "G"
        assert capo_fret_for_shape(perfect["key"], shape) == 1

    def test_g_shapes_are_the_lowest_fret_option(self, perfect, subtests):
        for other in ("E", "A", "D", "C", "F", "Bb", "Eb"):
            with subtests.test(shape=other):
                assert capo_fret_for_shape(perfect["key"], other) > 1

    def test_practice_key_g_is_still_selectable(self, perfect, subtests):
        for label, options in (("display", display_key_options(perfect["key"])),
                               ("conventional", conventional_key_options(perfect["key"]))):
            with subtests.test(list=label):
                assert "G" in options

    def test_practice_key_g_reproduces_the_previous_chart(self, perfect, subtests):
        """Anyone who prefers the old G chart just sets the Practice Key to G.

        Each level comes back as its OWN previous chart - Beginner and
        Intermediate as plain triads/sevenths, Advanced with its extensions.
        """
        expect = {
            "Beginner": (["G", "G", "Em7", "Em7"], ["Em7", "Cadd9", "G", "D/F#"]),
            "Intermediate": (["G", "G", "Em7", "Em7"], ["Em7", "Cadd9", "G", "D/F#"]),
            "Advanced": (["G6", "G6", "Em9", "Em9"], ["Em9", "C6/9", "Gmaj9/B", "D13sus4"]),
        }
        for lvl, secs in perfect["chart_versions"].items():
            with subtests.test(level=lvl):
                back = transpose_sections_dict(secs, "Ab", "G")
                want_verse, want_chorus = expect[lvl]
                assert back["Verse 1"][:4] == want_verse
                assert back["Chorus 1"][:4] == want_chorus


class TestWindPlayersNowMatchTheRecord:
    def test_flute_is_concert_pitch_so_it_reads_ab(self, perfect):
        """Flute does not transpose: the chart key IS what the flautist plays."""
        assert not is_transposing_instrument("Flute")
        assert perfect["key"] == "Ab"

    def test_saxophones_read_their_proper_written_keys(self, perfect, subtests):
        """Concert Ab -> Bb on a Bb sax (+2), F on an Eb sax (+9)."""
        expected = {"Soprano Saxophone": "Bb", "Tenor Saxophone": "Bb",
                    "Alto Saxophone": "F", "Baritone Saxophone": "F"}
        for display in saxophone_display_names():
            with subtests.test(sax=display):
                sax_type = saxophone_type_for_display_name(display)
                assert written_key_for_saxophone(perfect["key"], sax_type) == expected[display]

    def test_the_written_keys_moved_up_with_the_concert_key(self, subtests):
        """The old G chart gave a tenor A and an alto E - both a semitone flat."""
        for display, old, new in (("Tenor Saxophone", "A", "Bb"),
                                  ("Alto Saxophone", "E", "F")):
            with subtests.test(sax=display):
                sax_type = saxophone_type_for_display_name(display)
                assert written_key_for_saxophone("G", sax_type) == old
                assert written_key_for_saxophone("Ab", sax_type) == new


class TestSavedChartsAreHandledCorrectly:
    """A saved copy of the old G chart must be recognised; a real edit must not."""

    def test_the_prior_g_revision_is_recorded_in_the_table(self, perfect):
        entries = PRIOR_REVISIONS.get(revision_key(perfect)) or ()
        assert (PRIOR_G_SECTIONS_FP, PRIOR_G_VERSIONS_FP) in entries

    def test_the_revision_key_is_the_expected_song(self, perfect):
        assert revision_key(perfect) == "pop|perfect|ed sheeran"

    def test_an_untouched_saved_g_chart_is_recognised_as_a_prior_revision(self, perfect):
        snap = {"sections": transpose_sections_dict(perfect["sections"], "Ab", "G"),
                "chart_versions": {lvl: transpose_sections_dict(s, "Ab", "G")
                                   for lvl, s in perfect["chart_versions"].items()}}
        assert is_known_prior_revision(snap, perfect)

    def test_an_untouched_saved_g_chart_refreshes_to_the_new_key(self, perfect):
        snap = {"sections": transpose_sections_dict(perfect["sections"], "Ab", "G"),
                "chart_versions": {lvl: transpose_sections_dict(s, "Ab", "G")
                                   for lvl, s in perfect["chart_versions"].items()},
                "pick_key": CATALOG_PICK, "title": "Perfect", "artist": "Ed Sheeran"}
        action, reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
        assert action == REFRESH, reason

    def test_a_stamped_unmodified_snapshot_refreshes(self, perfect):
        g_secs = transpose_sections_dict(perfect["sections"], "Ab", "G")
        snap = {"sections": g_secs, "pick_key": CATALOG_PICK,
                CHART_ORIGIN_KEY: ORIGIN_CATALOG,
                CATALOG_REVISION_KEY: chart_fingerprint(g_secs)}
        action, reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
        assert action == REFRESH, reason

    def test_a_genuinely_edited_chart_is_kept(self, perfect):
        """A user who changed one chord keeps their work - no silent overwrite."""
        edited = {k: list(v) for k, v in
                  transpose_sections_dict(perfect["sections"], "Ab", "G").items()}
        edited["Verse 1"][0] = "Bm7"
        snap = {"sections": edited, "pick_key": CATALOG_PICK,
                "title": "Perfect", "artist": "Ed Sheeran"}
        action, reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
        assert action == KEEP, reason

    def test_an_edited_chart_that_was_stamped_is_kept(self, perfect):
        g_secs = transpose_sections_dict(perfect["sections"], "Ab", "G")
        edited = {k: list(v) for k, v in g_secs.items()}
        edited["Chorus 1"][0] = "Fmaj7"
        snap = {"sections": edited, "pick_key": CATALOG_PICK,
                CHART_ORIGIN_KEY: ORIGIN_CATALOG,
                CATALOG_REVISION_KEY: chart_fingerprint(g_secs)}
        action, reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
        assert action == KEEP, reason

    def test_an_edit_marked_chart_is_kept(self, perfect, subtests):
        g_secs = transpose_sections_dict(perfect["sections"], "Ab", "G")
        for marker in ("user_edited", "user_override", "arrangement_customized"):
            with subtests.test(marker=marker):
                snap = {"sections": g_secs, "pick_key": CATALOG_PICK, marker: True}
                action, reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
                assert action == KEEP, reason

    def test_a_custom_or_composition_chart_is_kept(self, perfect, subtests):
        g_secs = transpose_sections_dict(perfect["sections"], "Ab", "G")
        for pick in ("custom::my-perfect", "composition::abc123"):
            with subtests.test(pick=pick):
                snap = {"sections": g_secs, "pick_key": pick}
                action, reason = classify_snapshot(snap, perfect, pick_key=pick)
                assert action == KEEP, reason

    def test_a_chart_already_in_ab_is_classified_same(self, perfect):
        snap = {"sections": perfect["sections"], "pick_key": CATALOG_PICK}
        action, _reason = classify_snapshot(snap, perfect, pick_key=CATALOG_PICK)
        assert action == "same"

    def test_the_new_fingerprints_are_the_known_values(self, perfect):
        assert chart_fingerprint(perfect["sections"]) == AB_SECTIONS_FP
        assert versions_fingerprint(perfect["chart_versions"]) == AB_VERSIONS_FP

    def test_the_new_fingerprints_are_not_the_old_ones(self, perfect):
        assert chart_fingerprint(perfect["sections"]) != PRIOR_G_SECTIONS_FP
        assert versions_fingerprint(perfect["chart_versions"]) != PRIOR_G_VERSIONS_FP


class TestTheTimingCorrectionSurvives:
    """The key change must not disturb the previous commit's work."""

    def test_the_tempo_is_still_the_dotted_quarter_pulse(self, perfect):
        ext = perfect["extensions"]
        assert ext["default_bpm"] == 63
        assert ext["time_signature"] == "6/8"
        timing = meter_timing(ext["default_bpm"], ext["time_signature"])
        assert timing.bar_sec == pytest.approx(1.9048, abs=1e-4)
        assert timing.compound is True

    def test_every_level_still_plays_the_whole_song(self, perfect, subtests):
        for level in ("Beginner", "Intermediate", "Advanced"):
            with subtests.test(level=level):
                assert keeps_full_form(perfect, level)
                _view, secs = resolve_level_chart(perfect, level)
                assert sum(len(v) for v in secs.values()) == 102
                assert len(secs) == 9

    def test_the_verse_chorus_harmonic_rhythm_still_holds(self, perfect, subtests):
        def runs(cells):
            out = []
            for c in cells:
                if out and out[-1][0] == c:
                    out[-1][1] += 1
                else:
                    out.append([c, 1])
            return {n for _c, n in out}

        for name in ("Verse 1", "Verse 2", "Verse 3", "Verse 4"):
            with subtests.test(section=name):
                assert runs(perfect["sections"][name]) == {2}
        for name in ("Chorus 1", "Chorus 2", "Chorus 3"):
            with subtests.test(section=name):
                assert runs(perfect["sections"][name]) == {1}

    def test_the_chord_events_still_validate(self, perfect):
        ext = perfect["extensions"]
        events = sections_dict_to_events(perfect["sections"],
                                         time_signature=ext["time_signature"],
                                         section_order=perfect["section_order"])
        assert len(events) == 102
        assert validate_chord_events(events, time_signature=ext["time_signature"]) == []

    def test_the_form_is_still_flagged_as_unverified(self, perfect):
        """4:23 recording vs 3:14 of chart - the notes must keep saying so."""
        notes = perfect["extensions"]["arrangement_notes"]
        assert "OPEN" in notes
        assert "4:23" in notes and "3:14" in notes
        assert perfect["extensions"]["chart_confidence"]["form"] != "high"

    def test_the_notes_explain_the_capo_relationship(self, perfect):
        notes = perfect["extensions"]["arrangement_notes"]
        assert "capo" in notes.lower()
        assert "CONCERT" in notes or "concert" in notes
        assert "Practice Key G" in notes
