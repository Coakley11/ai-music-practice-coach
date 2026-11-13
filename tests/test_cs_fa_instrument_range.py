"""Generated melodies stay inside the selected instrument's sounding range, with sound spelling."""
import re
import unittest

from composition_document import (
    apply_section_chords, apply_structure_template, bootstrap_from_vision, ordered_sections, parse_chord_paste,
)
from composition_melody_projection import concert_melody_range
from composition_melody_suggestions import fit_events_to_range, suggest_melody_concepts
from media_tone_catalog import parse_note_token

INSTRUMENTS = {  # (instrument as Practice stores it, selected transposing type)
    "Flute": "",
    "Saxophone/alto": "Alto saxophone (Eb)",
    "Saxophone/tenor": "Tenor saxophone (Bb)",
    "Saxophone/soprano": "Soprano saxophone (Bb)",
    "Saxophone/baritone": "Baritone saxophone (Eb)",
    "Clarinet": "",
    "Trumpet": "",
    "Guitar": "",
}


def _session(label, t_type):
    inst = label.split("/")[0]
    ss = {"instrument": inst}
    if t_type:
        ss["selected_transposing_instrument"] = t_type
        ss["saxophone_type"] = t_type
    return inst, ss


PROGS = [("C major", "C Am F G"), ("A minor", "Am F C E7"), ("Bb major", "Bb Gm Eb F7"), ("E major", "E C#m A B7"),
         ("F# minor", "F#m D A E")]


def _doc(key, prog):
    d = bootstrap_from_vision(genre="Pop", song_idea="x", key=key, bpm=100, meter="4/4")
    apply_structure_template(d, "simple")
    s = ordered_sections(d)[0]
    apply_section_chords(d, str(s["id"]), parse_chord_paste(prog))
    return d, s


class TestInstrumentRange(unittest.TestCase):
    def test_windows(self) -> None:
        self.assertIsNone(concert_melody_range("Piano"))
        self.assertIsNone(concert_melody_range(""))
        self.assertGreaterEqual(concert_melody_range("Flute")[0], 60)
        inst, ss = _session("Saxophone/tenor", "Tenor saxophone (Bb)")
        # written ceiling 90 minus 14 semitones (Bb + octave)
        self.assertLessEqual(concert_melody_range(inst, ss)[1], 76)
        inst, ss = _session("Saxophone/alto", "Alto saxophone (Eb)")
        self.assertLessEqual(concert_melody_range(inst, ss)[1], 79)

    def test_every_generated_note_in_range_and_spelled(self) -> None:
        for label, t_type in INSTRUMENTS.items():
            inst, ss = _session(label, t_type)
            rng = concert_melody_range(inst, ss)
            self.assertIsNotNone(rng, label)
            for key, prog in PROGS:
                doc, sec = _doc(key, prog)
                for feel in ("lyrical", "bold", "emotional"):
                    for style in ("simple", "complex"):
                        concepts = suggest_melody_concepts(doc, sec, feel, style, limit=3, range_midi=rng)
                        self.assertTrue(concepts, (inst, key))
                        for c in concepts:
                            for ev in c["events"]:
                                if ev.get("is_rest") or str(ev.get("pitch")).lower() == "rest":
                                    continue
                                m = parse_note_token(ev["pitch"])
                                self.assertIsNotNone(m)
                                self.assertEqual(m, int(ev["midi"]), (inst, key, ev))
                                self.assertTrue(rng[0] <= m <= rng[1], (inst, key, feel, style, ev, rng))
                                self.assertRegex(ev["pitch"], r"^[A-G][#b]?-?\d$")

    def test_fit_keeps_spelling_and_pitch_class(self) -> None:
        evs = [{"pitch": "F#6", "midi": 90, "duration_beats": 1.0}, {"pitch": "Bb2", "midi": 46, "duration_beats": 1.0},
               {"pitch": "rest", "is_rest": True, "duration_beats": 1.0}, {"pitch": "C5", "midi": 72}]
        out = fit_events_to_range(evs, 60, 79)
        self.assertEqual([e["pitch"] for e in out], ["F#5", "Bb4", "rest", "C5"])
        self.assertEqual([e.get("midi") for e in out], [78, 70, None, 72])
        for a, b in zip(evs, out):
            if a.get("midi") is not None:
                self.assertEqual((a["midi"] - b["midi"]) % 12, 0)

    def test_default_unchanged_without_range(self) -> None:
        doc, sec = _doc("C major", "C Am F G")
        a = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=3)
        b = suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=3, range_midi=None)
        self.assertEqual([c["events"] for c in a], [c["events"] for c in b])


if __name__ == "__main__":
    unittest.main()
