"""Tests for CPL inline chord editing (click-to-edit)."""

from __future__ import annotations

import unittest

from custom_progression_lab import (
    apply_quick_chord_edit,
    cpl_collapse_identical_adjacent,
    cpl_copy_chord_range,
    cpl_expand_chord_group,
    cpl_paste_at_position,
    cpl_remove_chord_at_index,
    cpl_replace_chord_in_section,
    cpl_split_measure_at_index,
    diatonic_roots_for_key,
    editable_chord_options_for_key,
    chromatic_roots_for_key,
    extract_chord_root_and_suffix,
    suggest_split_second_chords,
    CHORD_EDIT_QUALITIES,
    CPL_RANGE_CLIPBOARD_KEY,
    default_active_progression,
    cpl_apply_chord_with_bars_to_session,
)


def _session_with_chords(chords: list[dict], section: str = "Verse") -> dict:
    from custom_progression_lab import default_active_progression

    ss: dict = {"cpl_active_progression": default_active_progression()}
    active = ss["cpl_active_progression"]
    active["original_sections"][section] = list(chords)
    ss["cpl_active_progression"] = active
    return ss


class TestEditableChordOptions(unittest.TestCase):
    def test_major_key_has_diatonic_triads(self) -> None:
        opts = editable_chord_options_for_key("C")
        for ch in ("C", "Dm", "Em", "F", "G", "Am"):
            self.assertIn(ch, opts)

    def test_major_key_has_seventh_chords(self) -> None:
        opts = editable_chord_options_for_key("C")
        for ch in ("Cmaj7", "Dm7", "G7"):
            self.assertIn(ch, opts)

    def test_minor_key_has_diatonic(self) -> None:
        opts = editable_chord_options_for_key("Am")
        for ch in ("Am", "C", "Dm", "Em", "F", "G"):
            self.assertIn(ch, opts)

    def test_minor_key_has_extensions(self) -> None:
        opts = editable_chord_options_for_key("Am")
        for ch in ("Am7", "G7"):
            self.assertIn(ch, opts)

    def test_no_duplicates(self) -> None:
        opts = editable_chord_options_for_key("G")
        self.assertEqual(len(opts), len(set(opts)))

    def test_transposed_key(self) -> None:
        opts = editable_chord_options_for_key("Eb")
        self.assertIn("Eb", opts)
        self.assertIn("Bb", opts)


class TestReplaceChordInSection(unittest.TestCase):
    def test_replace_simple_chord(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 2},
        ])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Am",
        )
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Am")
        self.assertEqual(entries[0]["bars"], 1)
        self.assertEqual(entries[1]["chord"], "G")
        self.assertEqual(entries[1]["bars"], 2)

    def test_replace_preserves_bars(self) -> None:
        ss = _session_with_chords([{"chord": "F", "bars": 4}])
        cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Dm7",
        )
        entry = ss["cpl_active_progression"]["original_sections"]["Verse"][0]
        self.assertEqual(entry["chord"], "Dm7")
        self.assertEqual(entry["bars"], 4)

    def test_replace_subdivided_chord(self) -> None:
        ss = _session_with_chords([{"chord": "C:2|G:2", "bars": 1}])
        cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="Am",
        )
        entry = ss["cpl_active_progression"]["original_sections"]["Verse"][0]
        self.assertIn("Am", entry["chord"])
        self.assertIn("G", entry["chord"])
        self.assertIn("|", entry["chord"])

    def test_out_of_bounds_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=5, new_chord="Am",
        )
        self.assertFalse(ok)

    def test_empty_chord_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_replace_chord_in_section(
            ss, section_name="Verse", index=0, new_chord="",
        )
        self.assertFalse(ok)


class TestChromaticRoots(unittest.TestCase):
    def test_twelve_roots(self) -> None:
        roots = chromatic_roots_for_key("C")
        self.assertEqual(len(roots), 12)

    def test_no_duplicates(self) -> None:
        roots = chromatic_roots_for_key("Fm")
        self.assertEqual(len(roots), len(set(roots)))

    def test_fm_includes_key_relevant_roots(self) -> None:
        roots = chromatic_roots_for_key("Fm")
        for note in ("F", "Ab", "Bb", "C", "Db", "Eb", "G"):
            self.assertIn(note, roots, f"{note} missing from Fm chromatic roots")


class TestExtractRootAndSuffix(unittest.TestCase):
    def test_major_triad(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("C"), ("C", ""))

    def test_minor_seventh(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("Dm7"), ("D", "m7"))

    def test_flat_root(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("Bbmaj7"), ("Bb", "maj7"))

    def test_sharp_root(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("F#m7b5"), ("F#", "m7b5"))

    def test_altered_dominant(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("G7b9"), ("G", "7b9"))

    def test_six_nine(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix("Db6/9"), ("Db", "6/9"))

    def test_empty(self) -> None:
        self.assertEqual(extract_chord_root_and_suffix(""), ("", ""))


class TestExpandedVocabulary(unittest.TestCase):
    def test_fm_has_borrowed_chords(self) -> None:
        opts = editable_chord_options_for_key("Fm")
        self.assertIn("C7", opts)
        self.assertIn("Bb", opts)
        self.assertIn("C7b9", opts)

    def test_c_major_has_borrowed_chords(self) -> None:
        opts = editable_chord_options_for_key("C")
        self.assertIn("Bb", opts)
        self.assertIn("Eb", opts)
        self.assertIn("Ab", opts)

    def test_qualities_include_all_requested(self) -> None:
        for q in ["mMaj7", "6/9", "11", "7b9", "7#9", "7#11", "7b13",
                   "maj9", "m11", "maj13", "m13"]:
            self.assertIn(q, CHORD_EDIT_QUALITIES, f"{q} missing from CHORD_EDIT_QUALITIES")


class TestChordSpellingPreservation(unittest.TestCase):
    """Verify chord quality and enharmonic spelling are preserved."""

    def test_fm6_remains_fm6(self) -> None:
        result = apply_quick_chord_edit("Fm", "6")
        self.assertEqual(result, "Fm6")

    def test_db7_remains_db7(self) -> None:
        result = apply_quick_chord_edit("Db", "7")
        self.assertEqual(result, "Db7")

    def test_bb_remains_bb(self) -> None:
        result = apply_quick_chord_edit("Bb", "maj7")
        self.assertEqual(result, "Bbmaj7")

    def test_minor_seventh(self) -> None:
        result = apply_quick_chord_edit("Am", "7")
        self.assertEqual(result, "Am7")

    def test_sharp_root_preserved(self) -> None:
        result = apply_quick_chord_edit("F#m", "7b5")
        self.assertEqual(result, "F#m7b5")

    def test_slash_chord_preserves_root(self) -> None:
        result = apply_quick_chord_edit("Db/F", "7")
        self.assertEqual(result, "Db7/F")

    def test_altered_dominant(self) -> None:
        result = apply_quick_chord_edit("Eb7", "7#9")
        self.assertEqual(result, "Eb7#9")

    def test_plain_major(self) -> None:
        result = apply_quick_chord_edit("C", "6")
        self.assertEqual(result, "C6")


class TestRemoveChord(unittest.TestCase):
    def test_remove_middle(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 1},
            {"chord": "Am", "bars": 1},
        ])
        ok = cpl_remove_chord_at_index(ss, section_name="Verse", index=1)
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["chord"], "C")
        self.assertEqual(entries[1]["chord"], "Am")

    def test_remove_only_chord(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_remove_chord_at_index(ss, section_name="Verse", index=0)
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 0)

    def test_remove_out_of_bounds(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_remove_chord_at_index(ss, section_name="Verse", index=5)
        self.assertFalse(ok)

    def test_remove_preserves_neighbors(self) -> None:
        ss = _session_with_chords([
            {"chord": "Fm6", "bars": 2},
            {"chord": "Db7", "bars": 1},
            {"chord": "C7", "bars": 1},
        ])
        cpl_remove_chord_at_index(ss, section_name="Verse", index=1)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[0]["bars"], 2)
        self.assertEqual(entries[1]["chord"], "C7")


class TestExpandChordGroup(unittest.TestCase):
    def test_expand_four_bars(self) -> None:
        ss = _session_with_chords([{"chord": "Fm6", "bars": 4}])
        ok = cpl_expand_chord_group(ss, section_name="Verse", index=0)
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 4)
        for e in entries:
            self.assertEqual(e["chord"], "Fm6")
            self.assertEqual(e["bars"], 1)

    def test_expand_preserves_total_length(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "Fm6", "bars": 3},
            {"chord": "G", "bars": 1},
        ])
        cpl_expand_chord_group(ss, section_name="Verse", index=1)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 5)
        self.assertEqual(entries[0]["chord"], "C")
        self.assertEqual(entries[1]["chord"], "Fm6")
        self.assertEqual(entries[2]["chord"], "Fm6")
        self.assertEqual(entries[3]["chord"], "Fm6")
        self.assertEqual(entries[4]["chord"], "G")

    def test_expand_single_bar_returns_false(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_expand_chord_group(ss, section_name="Verse", index=0)
        self.assertFalse(ok)

    def test_edit_after_expand(self) -> None:
        """Expand Fm6 x4, then change measure 4 to F6."""
        ss = _session_with_chords([{"chord": "Fm6", "bars": 4}])
        cpl_expand_chord_group(ss, section_name="Verse", index=0)
        cpl_replace_chord_in_section(ss, section_name="Verse", index=3, new_chord="F6")
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[1]["chord"], "Fm6")
        self.assertEqual(entries[2]["chord"], "Fm6")
        self.assertEqual(entries[3]["chord"], "F6")

    def test_edit_middle_measure_after_expand(self) -> None:
        """Expand Fm6 x4, then change measure 2 to Db7."""
        ss = _session_with_chords([{"chord": "Fm6", "bars": 4}])
        cpl_expand_chord_group(ss, section_name="Verse", index=0)
        cpl_replace_chord_in_section(ss, section_name="Verse", index=1, new_chord="Db7")
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[1]["chord"], "Db7")
        self.assertEqual(entries[2]["chord"], "Fm6")
        self.assertEqual(entries[3]["chord"], "Fm6")


class TestCollapseIdenticalAdjacent(unittest.TestCase):
    def test_collapse_four_identical(self) -> None:
        ss = _session_with_chords([
            {"chord": "Fm6", "bars": 1},
            {"chord": "Fm6", "bars": 1},
            {"chord": "Fm6", "bars": 1},
            {"chord": "Fm6", "bars": 1},
        ])
        removed = cpl_collapse_identical_adjacent(ss, section_name="Verse")
        self.assertEqual(removed, 3)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["chord"], "Fm6")
        self.assertEqual(entries[0]["bars"], 4)

    def test_collapse_mixed(self) -> None:
        ss = _session_with_chords([
            {"chord": "Fm6", "bars": 1},
            {"chord": "Fm6", "bars": 1},
            {"chord": "Db7", "bars": 1},
            {"chord": "C7", "bars": 1},
        ])
        removed = cpl_collapse_identical_adjacent(ss, section_name="Verse")
        self.assertEqual(removed, 1)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["bars"], 2)

    def test_collapse_nothing_to_combine(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 1},
        ])
        removed = cpl_collapse_identical_adjacent(ss, section_name="Verse")
        self.assertEqual(removed, 0)


class TestCopyChordRange(unittest.TestCase):
    def test_copy_range(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "Dm7", "bars": 1},
            {"chord": "G7", "bars": 1},
            {"chord": "Cmaj7", "bars": 1},
        ])
        ok = cpl_copy_chord_range(ss, section_name="Verse", start=1, end=2)
        self.assertTrue(ok)
        clip = ss[CPL_RANGE_CLIPBOARD_KEY]
        self.assertEqual(len(clip), 2)
        self.assertEqual(clip[0]["chord"], "Dm7")
        self.assertEqual(clip[1]["chord"], "G7")

    def test_copy_single_chord(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "G", "bars": 1},
        ])
        ok = cpl_copy_chord_range(ss, section_name="Verse", start=0, end=0)
        self.assertTrue(ok)
        self.assertEqual(len(ss[CPL_RANGE_CLIPBOARD_KEY]), 1)

    def test_copy_invalid_range(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_copy_chord_range(ss, section_name="Verse", start=0, end=5)
        self.assertFalse(ok)

    def test_copy_split_measures(self) -> None:
        ss = _session_with_chords([
            {"chord": "C:2|G:2", "bars": 1},
            {"chord": "Am", "bars": 1},
        ])
        ok = cpl_copy_chord_range(ss, section_name="Verse", start=0, end=1)
        self.assertTrue(ok)
        self.assertEqual(ss[CPL_RANGE_CLIPBOARD_KEY][0]["chord"], "C:2|G:2")


class TestPasteAtPosition(unittest.TestCase):
    def test_paste_middle(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "Am", "bars": 1},
        ])
        ss[CPL_RANGE_CLIPBOARD_KEY] = [
            {"chord": "Dm7", "bars": 1},
            {"chord": "G7", "bars": 1},
        ]
        ok = cpl_paste_at_position(ss, section_name="Verse", position=1)
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[0]["chord"], "C")
        self.assertEqual(entries[1]["chord"], "Dm7")
        self.assertEqual(entries[2]["chord"], "G7")
        self.assertEqual(entries[3]["chord"], "Am")

    def test_paste_at_end(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ss[CPL_RANGE_CLIPBOARD_KEY] = [{"chord": "G", "bars": 1}]
        cpl_paste_at_position(ss, section_name="Verse", position=99)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["chord"], "G")

    def test_paste_at_start(self) -> None:
        ss = _session_with_chords([{"chord": "Am", "bars": 1}])
        ss[CPL_RANGE_CLIPBOARD_KEY] = [{"chord": "Dm", "bars": 1}]
        cpl_paste_at_position(ss, section_name="Verse", position=0)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Dm")
        self.assertEqual(entries[1]["chord"], "Am")


class TestSplitMeasureAtIndex(unittest.TestCase):
    def test_split_2_plus_2(self) -> None:
        ss = _session_with_chords([
            {"chord": "C", "bars": 1},
            {"chord": "Fm6", "bars": 1},
        ])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=1, pattern="2+2", second_chord="Db7",
        )
        self.assertTrue(ok)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 2)
        self.assertIn("Fm6", entries[1]["chord"])
        self.assertIn("Db7", entries[1]["chord"])
        self.assertIn("|", entries[1]["chord"])

    def test_split_3_plus_1(self) -> None:
        ss = _session_with_chords([{"chord": "Db7", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0, pattern="3+1", second_chord="C7",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Db7", chord)
        self.assertIn("C7", chord)

    def test_split_preserves_neighbors(self) -> None:
        ss = _session_with_chords([
            {"chord": "Am", "bars": 1},
            {"chord": "F", "bars": 1},
            {"chord": "G", "bars": 1},
        ])
        cpl_split_measure_at_index(
            ss, section_name="Verse", index=1, pattern="2+2", second_chord="C",
        )
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(entries[0]["chord"], "Am")
        self.assertEqual(entries[2]["chord"], "G")
        self.assertIn("|", entries[1]["chord"])


class TestDiatonicRoots(unittest.TestCase):
    def test_gm_diatonic_roots_are_notes_only(self) -> None:
        roots = diatonic_roots_for_key("Gm")
        for r in roots:
            self.assertNotIn("m", r.lower().replace("m", "", 1) if len(r) > 1 and r[1:].startswith("m") else "")
            self.assertRegex(r, r"^[A-G][#b]?$")

    def test_gm_has_seven_roots(self) -> None:
        roots = diatonic_roots_for_key("Gm")
        self.assertEqual(len(roots), 7)

    def test_gm_includes_bb(self) -> None:
        roots = diatonic_roots_for_key("Gm")
        self.assertIn("Bb", roots)

    def test_c_major_diatonic(self) -> None:
        roots = diatonic_roots_for_key("C")
        self.assertEqual(len(roots), 7)
        for note in ("C", "D", "E", "F", "G", "A", "B"):
            self.assertIn(note, roots)

    def test_roots_preserve_flat_spelling(self) -> None:
        roots = diatonic_roots_for_key("Fm")
        self.assertIn("Db", roots)
        self.assertIn("Eb", roots)
        self.assertIn("Ab", roots)


class TestChordBuilderCombinations(unittest.TestCase):
    """Test the chord assembly logic the UI chord builder uses."""

    def test_g_minor(self) -> None:
        self.assertEqual(apply_quick_chord_edit("G", "m"), "Gm")

    def test_g_minor_6(self) -> None:
        self.assertEqual(apply_quick_chord_edit("Gm", "6"), "Gm6")

    def test_a_dim(self) -> None:
        self.assertEqual(apply_quick_chord_edit("A", "dim"), "Adim")

    def test_bb_dim(self) -> None:
        self.assertEqual(apply_quick_chord_edit("Bb", "dim"), "Bbdim")

    def test_c_minor(self) -> None:
        self.assertEqual(apply_quick_chord_edit("C", "m"), "Cm")

    def test_d_aug(self) -> None:
        self.assertEqual(apply_quick_chord_edit("D", "aug"), "Daug")

    def test_eb_7(self) -> None:
        self.assertEqual(apply_quick_chord_edit("Eb", "7"), "Eb7")

    def test_bb_maj7(self) -> None:
        self.assertEqual(apply_quick_chord_edit("Bb", "maj7"), "Bbmaj7")

    def test_minor_to_dim_replaces(self) -> None:
        self.assertEqual(apply_quick_chord_edit("Am", "dim"), "Adim")

    def test_major_to_m7(self) -> None:
        self.assertEqual(apply_quick_chord_edit("C", "m7"), "Cm7")


class TestSplitWithFirstChordOverride(unittest.TestCase):
    """Tests for the first_chord parameter allowing any chord in split positions."""

    def test_gmadd9_split_3_plus_1_with_c7b9(self) -> None:
        ss = _session_with_chords([{"chord": "Gmadd9", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="3+1", first_chord="Gmadd9", second_chord="C7b9",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Gmadd9", chord)
        self.assertIn("C7b9", chord)
        self.assertIn("|", chord)

    def test_fm6_split_2_plus_2_with_db7(self) -> None:
        ss = _session_with_chords([{"chord": "Fm6", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="2+2", first_chord="Fm6", second_chord="Db7",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Fm6", chord)
        self.assertIn("Db7", chord)

    def test_bbmaj9_split_3_plus_1_with_eb13(self) -> None:
        ss = _session_with_chords([{"chord": "Bbmaj9", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="3+1", first_chord="Bbmaj9", second_chord="Eb13",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Bbmaj9", chord)
        self.assertIn("Eb13", chord)

    def test_slash_chord_in_split(self) -> None:
        ss = _session_with_chords([{"chord": "Gm7/Bb", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="2+2", first_chord="Gm7/Bb", second_chord="C7#9",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Gm7/Bb", chord)
        self.assertIn("C7#9", chord)

    def test_first_chord_override_replaces_existing(self) -> None:
        ss = _session_with_chords([{"chord": "Am", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="2+2", first_chord="Dm9", second_chord="G7",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Dm9", chord)
        self.assertIn("G7", chord)
        self.assertNotIn("Am", chord)

    def test_empty_first_chord_uses_existing(self) -> None:
        ss = _session_with_chords([{"chord": "Gmadd9", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="3+1", first_chord="", second_chord="C7b9",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Gmadd9", chord)
        self.assertIn("C7b9", chord)

    def test_split_preserves_enharmonic_spelling(self) -> None:
        ss = _session_with_chords([{"chord": "Db7", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="2+2", first_chord="Db7", second_chord="Bbm",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Db7", chord)
        self.assertIn("Bbm", chord)
        self.assertNotIn("C#", chord)

    def test_save_reload_split_with_extensions(self) -> None:
        from custom_progression_lab import cpl_save_draft
        ss = _session_with_chords([{"chord": "Gmadd9", "bars": 1}])
        cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="3+1", first_chord="Gmadd9", second_chord="C7b9",
        )
        active = ss["cpl_active_progression"]
        home = active["original_sections"]
        cpl_save_draft(ss, active, home, persist=True, st=None)
        chord_after = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Gmadd9", chord_after)
        self.assertIn("C7b9", chord_after)

    def test_edit_already_split_measure(self) -> None:
        ss = _session_with_chords([{"chord": "Am:2|G:2", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="3+1", first_chord="Bbmaj9", second_chord="Eb13",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Bbmaj9", chord)
        self.assertIn("Eb13", chord)
        self.assertNotIn("Am", chord)

    def test_4x1_uses_first_chord_param(self) -> None:
        ss = _session_with_chords([{"chord": "C", "bars": 1}])
        ok = cpl_split_measure_at_index(
            ss, section_name="Verse", index=0,
            pattern="4x1", first_chord="Fm6", second_chord="Db7",
        )
        self.assertTrue(ok)
        chord = ss["cpl_active_progression"]["original_sections"]["Verse"][0]["chord"]
        self.assertIn("Fm6", chord)
        self.assertIn("Db7", chord)


class TestSuggestSplitSecondChords(unittest.TestCase):
    """Context-aware split second-chord suggestions."""

    def test_dm7_before_cmaj7_in_c_major(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Dm7", next_chord="Cmaj7", prev_chord="",
            home_key="C", style="Pop",
        )
        chords = [ch for ch, _ in result]
        self.assertIn("G7", chords, "V7 should lead into Cmaj7")
        self.assertEqual(chords[0], "G7", "G7 should be top suggestion")

    def test_fm_context_suggests_c7(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Fm", next_chord="Fm", prev_chord="Bbm",
            home_key="Fm", style="Pop",
        )
        chords = [ch for ch, _ in result]
        self.assertIn("C7", chords, "V7 of Fm should be suggested")

    def test_fm_jazz_suggests_c7b9(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Fm", next_chord="Fm", prev_chord="Bbm",
            home_key="Fm", style="Jazz",
        )
        chords = [ch for ch, _ in result]
        self.assertTrue(
            any("C7" in c for c in chords),
            "Jazz Fm context should suggest dominant approach",
        )

    def test_blues_style_suggests_dominant_seventh(self) -> None:
        result = suggest_split_second_chords(
            current_chord="C7", next_chord="F7", prev_chord="",
            home_key="C", style="Blues",
        )
        chords = [ch for ch, _ in result]
        self.assertTrue(len(chords) >= 2, "Should have multiple suggestions")
        self.assertTrue(
            any("7" in c for c in chords),
            "Blues should suggest dominant chords",
        )

    def test_pop_style_prefers_simple_chords(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Am", next_chord="F", prev_chord="C",
            home_key="C", style="Pop",
        )
        chords = [ch for ch, _ in result]
        self.assertTrue(len(chords) >= 2)
        has_dim = any("dim" in c for c in chords[:2])
        has_b9 = any("b9" in c for c in chords[:2])
        self.assertFalse(has_dim and has_b9, "Pop top picks shouldn't be complex jazz chords")

    def test_keeps_unchanged_option(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Gm", next_chord="C7", prev_chord="Dm",
            home_key="Gm", style="Pop",
        )
        chords = [ch for ch, _ in result]
        self.assertIn("Gm", chords, "Unchanged chord should be an option")

    def test_no_next_chord_still_suggests(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Am", next_chord="", prev_chord="G",
            home_key="C", style="Pop",
        )
        self.assertTrue(len(result) >= 1, "Should still suggest even without next chord")

    def test_reasons_are_musician_friendly(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Dm7", next_chord="Cmaj7", prev_chord="",
            home_key="C", style="Jazz",
        )
        for _, reason in result:
            self.assertTrue(len(reason) > 0, "Each suggestion should have a reason")
            self.assertTrue(len(reason) < 80, f"Reason too long: {reason}")

    def test_jazz_suggests_ii_v(self) -> None:
        result = suggest_split_second_chords(
            current_chord="Cmaj7", next_chord="Am7", prev_chord="Dm7",
            home_key="C", style="Jazz",
        )
        chords = [ch for ch, _ in result]
        self.assertIn("E7", chords, "V7/vi should approach Am7 in jazz")

    def test_different_keys_produce_different_suggestions(self) -> None:
        result_c = suggest_split_second_chords(
            current_chord="Dm7", next_chord="C", prev_chord="",
            home_key="C", style="Pop",
        )
        result_g = suggest_split_second_chords(
            current_chord="Am7", next_chord="G", prev_chord="",
            home_key="G", style="Pop",
        )
        top_c = result_c[0][0] if result_c else ""
        top_g = result_g[0][0] if result_g else ""
        self.assertNotEqual(top_c, top_g, "Different keys should produce different chord names")


class TestSaveReloadRoundTrip(unittest.TestCase):
    def test_edited_progression_survives_save(self) -> None:
        from custom_progression_lab import cpl_save_draft
        ss = _session_with_chords([{"chord": "Fm6", "bars": 4}])
        cpl_expand_chord_group(ss, section_name="Verse", index=0)
        cpl_replace_chord_in_section(ss, section_name="Verse", index=3, new_chord="F6")
        active = ss["cpl_active_progression"]
        home = active["original_sections"]
        cpl_save_draft(ss, active, home, persist=True, st=None)
        entries = ss["cpl_active_progression"]["original_sections"]["Verse"]
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[3]["chord"], "F6")
        self.assertEqual(entries[0]["chord"], "Fm6")


if __name__ == "__main__":
    unittest.main()
