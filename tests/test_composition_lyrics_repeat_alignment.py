"""Provisional lyric alignment with Melody repeats (2026-11-19).

When the lyrics ran out in pass 1, the last syllable was held (melisma) across the whole repeated pass.
Each repeated pass now starts a new phrase: its notes stay untexted unless lyrics remain for them.
"""

import json
import unittest

from composition_document import (
    apply_melody_concept,
    apply_section_chords,
    apply_structure_template,
    bootstrap_from_vision,
    ordered_sections,
    parse_chord_paste,
)
from composition_lyrics_alignment import (
    align_lyrics_to_melody,
    align_section,
    get_alignment,
    realign_section,
    refresh_section_alignment_status,
)
from composition_melody_repeats import set_section_melody_repeats
from composition_melody_suggestions import suggest_melody_concepts


def _section(repeats: int, lyrics: str):
    doc = bootstrap_from_vision(genre="Pop", song_idea="Align repeats.")
    apply_structure_template(doc, "simple")
    sec = ordered_sections(doc)[0]
    sid = str(sec["id"])
    apply_section_chords(doc, sid, parse_chord_paste("D Bm G A"))
    apply_melody_concept(doc, sid, suggest_melody_concepts(doc, sec, "lyrical", "simple", limit=1)[0])
    if repeats > 1:
        set_section_melody_repeats(doc, sid, repeats)
    sec = next(s for s in ordered_sections(doc) if str(s["id"]) == sid)
    sec.setdefault("lyrics", {})["raw_text"] = lyrics
    return doc, sec, sid


def _pass_types(sec, alignment):
    out: dict = {}
    for ev, a in zip(sec["melody"]["events"], alignment["event_assignments"]):
        out.setdefault(ev.get("repeat_index"), []).append(a["type"])
    return out


class TestRepeatAlignment(unittest.TestCase):
    def test_short_lyrics_do_not_hold_into_the_repeated_pass(self) -> None:
        _doc, sec, _sid = _section(2, "Morning light is falling")
        types = _pass_types(sec, align_lyrics_to_melody(sec["lyrics"]["raw_text"], sec["melody"]["events"]))
        self.assertIn("syllable", types[0])
        self.assertNotIn("melisma", types[1])
        self.assertNotIn("syllable", types[1])

    def test_lyrics_long_enough_continue_into_the_repeated_pass(self) -> None:
        words = " ".join(["la"] * 20)
        _doc, sec, _sid = _section(2, words)
        types = _pass_types(sec, align_lyrics_to_melody(words, sec["melody"]["events"]))
        self.assertIn("syllable", types[1])

    def test_single_pass_alignment_is_unchanged(self) -> None:
        _doc, sec, _sid = _section(1, "Morning light is falling")
        a = align_lyrics_to_melody(sec["lyrics"]["raw_text"], sec["melody"]["events"])
        self.assertEqual([x["type"] for x in a["event_assignments"]].count("unassigned"), 0)

    def test_save_reopen_keeps_alignment_and_repeats_mark_it_stale(self) -> None:
        doc, sec, sid = _section(1, "Morning light is falling\nOn the quiet street")
        before = json.loads(json.dumps(align_section(sec)))
        reopened = json.loads(json.dumps(doc))
        rsec = next(s for s in ordered_sections(reopened) if str(s["id"]) == sid)
        self.assertFalse(refresh_section_alignment_status(rsec))
        self.assertEqual(get_alignment(rsec)["event_assignments"], before["event_assignments"])
        self.assertEqual(get_alignment(rsec)["status"], "provisional")
        set_section_melody_repeats(reopened, sid, 2)
        rsec = next(s for s in ordered_sections(reopened) if str(s["id"]) == sid)
        refresh_section_alignment_status(rsec)
        self.assertEqual(get_alignment(rsec)["status"], "stale")
        realigned = realign_section(rsec)
        self.assertEqual(len(realigned["event_assignments"]), len(rsec["melody"]["events"]))


if __name__ == "__main__":
    unittest.main()
