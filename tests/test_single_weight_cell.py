"""A lone weighted cell (``C:4``, ``B:2``) is chord X, never a chord named ``C:4``.

Semantics: a ``:weight`` is only meaningful relative to sibling chords in a
``|`` split. On its own the token is chord X filling the whole bar (exactly how
the synth has always played it), so the weight is stripped from the chord name
and the parsed weight stays ``beats_per_bar`` (timing byte-identical).

Pipe cells (``A|B``, ``A:3|B:1``, ``A:3.5|B:0.5p``) and plain cells are not
touched; ``_legacy_parse`` below is the pre-fix single-token branch and the
whole-catalog test proves every non-lone cell parses identically.
"""

from __future__ import annotations

import copy
import unittest

import chord_subdivisions as cs
from chart_level_arrangement import resolve_level_chart
from chord_events import beats_per_bar_from_signature, sections_dict_to_events, validate_chord_events
from chord_subdivisions import (
    Subdivision,
    bare_chord_token,
    chord_names_label,
    chord_stream,
    parse_subdivisions,
    primary_chord,
    subdivisions,
)
from song_catalog.catalog import _merge_records

SAY_VERSE = ["G:3.5|C:0.5p", "C:4", "Em:3.5|D:0.5p", "D:4"]


def _legacy_parse(token, beats_per_bar=4.0):
    """Pre-fix behaviour for any cell that is not a lone ``X:w``."""
    raw = str(token or "").strip()
    if not raw:
        return []
    if "|" not in raw:
        chord_clean, push = cs._strip_push_marker(raw)
        if not chord_clean:
            return []
        return [Subdivision(chord=chord_clean, weight=float(beats_per_bar), push=push)]
    return parse_subdivisions(raw, beats_per_bar=beats_per_bar)  # pipe branch: code untouched


class ParserTests(unittest.TestCase):
    def test_lone_weight_is_chord_filling_bar(self) -> None:
        self.assertEqual(parse_subdivisions("C:4"), [Subdivision("C", 4.0, False)])
        self.assertEqual(parse_subdivisions("Am:4"), [Subdivision("Am", 4.0, False)])
        self.assertEqual(parse_subdivisions("C7:4"), [Subdivision("C7", 4.0, False)])
        # Weight 2 inside 4/4 (California Dreamin'): bar is still filled, as audio always did.
        self.assertEqual(parse_subdivisions("B:2"), [Subdivision("B", 4.0, False)])
        self.assertEqual(parse_subdivisions("C#m7:2"), [Subdivision("C#m7", 4.0, False)])
        self.assertEqual(parse_subdivisions("Badd9:2", beats_per_bar=3.0), [Subdivision("Badd9", 3.0, False)])

    def test_helpers(self) -> None:
        self.assertEqual(bare_chord_token("C:4"), "C")
        self.assertEqual(bare_chord_token(" D:4 "), "D")
        self.assertEqual(subdivisions("C:4"), ["C"])
        self.assertEqual(primary_chord("Em:4"), "Em")
        self.assertEqual(chord_names_label("C:4"), "C")
        self.assertEqual(chord_stream(["G:3.5|C:0.5p", "C:4", "D"]), ["G", "C", "C", "D"])

    def test_non_weight_tokens_untouched(self) -> None:
        for tok in ("C", "Cmaj7", "C/G", "N.C.", "Bm.hit", "C:x", "A|B", "A:3|B:1", "A:3.5|B:0.5p"):
            self.assertEqual(bare_chord_token(tok), tok)
        self.assertEqual(parse_subdivisions("C:x")[0].chord, "C:x")
        self.assertEqual(
            parse_subdivisions("A:3.5|B:0.5p"),
            [Subdivision("A", 3.5, False), Subdivision("B", 0.5, True)],
        )
        self.assertEqual(
            parse_subdivisions("A:3|B:1"), [Subdivision("A", 3.0, False), Subdivision("B", 1.0, False)]
        )
        self.assertEqual(
            parse_subdivisions("A|B"), [Subdivision("A", 2.0, False), Subdivision("B", 2.0, False)]
        )


class ConsumerTests(unittest.TestCase):
    def test_chord_events(self) -> None:
        ev = sections_dict_to_events({"Verse 1": SAY_VERSE})
        self.assertEqual([e["chord"] for e in ev], ["G", "C", "C", "Em", "D", "D"])
        self.assertEqual(validate_chord_events(ev), [])

    def test_backing_chart_lead_sheet_html(self) -> None:
        from songs.backing_chart import chart_grid_html

        html_out = chart_grid_html(SAY_VERSE, section_name="Verse 1")
        self.assertNotIn("C:4", html_out)
        self.assertNotIn("D:4", html_out)
        self.assertIn("<div class='chord-symbol'>C</div>", html_out)
        self.assertIn("<div class='chord-symbol'>D</div>", html_out)
        self.assertIn("Pushed change", html_out)  # push cells unchanged
        # no spurious "shape" hint just because the token carried a weight
        shaped = chart_grid_html(["C:4", "D:4"], shape_chords=["C", "D"])
        self.assertNotIn("shape</div>", shaped)

    def test_app_lead_sheet_html_and_timeline(self) -> None:
        import streamlit_music_practice_app as app

        html_out = app._chart_grid_html(SAY_VERSE, section_name="Verse 1")
        self.assertNotIn("C:4", html_out)
        self.assertNotIn("D:4", html_out)
        self.assertIn("data-chord='C'", html_out)
        self.assertIn("<div class='chord-symbol'>C</div>", html_out)

        raw_events = [
            {"chord": tok, "section": "Verse 1", "bar_in_section": i, "section_bars": 4}
            for i, tok in enumerate(SAY_VERSE)
        ]
        timeline = app.build_chord_event_timeline(raw_events, 80, 1)
        names = [t["chord"] for t in timeline]
        self.assertEqual(names, ["G", "C", "C", "Em", "D", "D"])
        self.assertEqual(timeline[2]["beat_duration"], 4.0)  # bar still fully filled

    def test_practice_notation_input(self) -> None:
        from practice_notation import generate_practice_notation

        for inst in ("Guitar", "Piano", "Bass", "Saxophone"):
            res = generate_practice_notation(
                song_title="Say", artist="John Mayer", display_key="G", original_key="G",
                bpm=80, groove_style="Pop groove", instrument=inst, focus="Chords",
                section_focus="Verse 1", sections={"Verse 1": ["C:4", "D:4", "Am:4", "G"]},
            )
            blob = repr(res)
            for bad in ("C:4", "D:4", "Am:4"):
                self.assertNotIn(bad, blob, f"{inst}: {bad}")


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cells = []  # (song, level, section, bar, token, bpb)
        for rec in _merge_records():
            bpb = beats_per_bar_from_signature(rec.get("time_signature") or "4/4")
            for lv in ("Beginner", "Intermediate", "Advanced"):
                try:
                    _, secs = resolve_level_chart(copy.deepcopy(rec), lv)
                except Exception:
                    continue
                for sec, bars in secs.items():
                    for i, tok in enumerate(bars):
                        cls.cells.append((rec["title"], lv, sec, i + 1, str(tok), bpb))

    def test_catalog_scale(self) -> None:
        self.assertGreater(len({c[0] for c in self.cells}), 100)

    def test_every_non_lone_cell_parses_exactly_as_before(self) -> None:
        n = 0
        for song, lv, sec, bar, tok, bpb in self.cells:
            if "|" not in tok and ":" in tok:
                continue
            n += 1
            self.assertEqual(
                parse_subdivisions(tok, beats_per_bar=bpb),
                _legacy_parse(tok, beats_per_bar=bpb),
                (song, lv, sec, bar, tok),
            )
        self.assertGreater(n, 15000)

    def test_lone_weight_cells_are_only_say_and_california_dreamin(self) -> None:
        lone = [c for c in self.cells if "|" not in c[4] and ":" in c[4]]
        self.assertEqual({c[0] for c in lone}, {"Say", "California Dreamin'"})
        for song, lv, sec, bar, tok, bpb in lone:
            chord, w = tok.split(":")
            subs = parse_subdivisions(tok, beats_per_bar=bpb)
            self.assertEqual(subs, [Subdivision(chord, bpb, False)], tok)
            if song == "Say":
                self.assertEqual(float(w), bpb, tok)  # weight == bar length
            else:
                self.assertEqual(float(w), 2.0)  # weight != bar length: data note, meaning not changed
        say = [c for c in lone if c[0] == "Say"]
        cd = [c for c in lone if c[0] != "Say"]
        self.assertGreater(len(say), 100)
        self.assertEqual(len(cd), 5)

    def test_no_catalog_cell_names_a_chord_with_a_colon(self) -> None:
        for song, lv, sec, bar, tok, bpb in self.cells:
            for s in parse_subdivisions(tok, beats_per_bar=bpb):
                self.assertNotIn(":", s.chord, (song, lv, sec, bar, tok))
            self.assertNotIn(":", chord_names_label(tok))


if __name__ == "__main__":
    unittest.main()
