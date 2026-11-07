"""Beginner chord simplification: valid symbols, preserved bar structure, no flipped quality."""

from __future__ import annotations

import re
import unittest

from chart_level_arrangement import resolve_level_chart
from chart_level_arrangement import simplify_chord_for_beginner as simp
from chord_events import sections_dict_to_events, validate_chord_events
from chord_subdivisions import parse_subdivisions
from music_theory import is_no_chord_token, spell_chord_tones, split_chord
from song_catalog.catalog import curated_song_records

# root + any combination of the quality tokens the catalog uses; optional slash bass.
CHORD_RE = re.compile(
    r"^[A-G][#b]?(?:maj|M|m|min|dim|aug|sus|add|alt|\d+|[#b]\d+|\+|/(?=\d))*(?:/[A-G][#b]?)?$"
)


def _chords(token):
    for sd in parse_subdivisions(token):
        c = sd.chord
        if c.lower().endswith(".hit"):
            c = c[:-4]
        yield c


def _family(chord):
    root, suf = split_chord(chord.split("/")[0])
    low = suf.lower()
    if "dim" in low or "m7b5" in low:
        return root, "dim"
    return root, ("min" if low.startswith("m") and not low.startswith("maj") else "maj")


class SimplifyUnitTests(unittest.TestCase):
    def test_no_chord_and_hits_pass_through(self):
        self.assertEqual(simp("N.C."), "N.C.")
        self.assertEqual(simp("E.hit"), "E.hit")
        self.assertEqual(simp("Emaj7.hit"), "E.hit")

    def test_beat_weights_and_pushes_survive(self):
        self.assertEqual(simp("Cmaj7:3|G7:1"), "C:3|G:1")
        self.assertEqual(simp("Bm7:2|Em7:2p"), "Bm:2|Em:2p")
        self.assertEqual(simp("Gmaj7:3.5|Cmaj7:0.5p"), "G:3.5|C:0.5p")
        self.assertEqual(simp("Dp"), "Dp")

    def test_major_seventh_is_not_minor(self):
        self.assertEqual(simp("CM7"), "C")
        self.assertEqual(simp("CmMaj7"), "Cm")
        self.assertEqual(simp("Cm7"), "Cm")

    def test_documented_edge_cases(self):
        self.assertEqual(simp("Dm7b5"), "Dm")  # half-diminished -> minor triad (established Beginner reading)
        self.assertEqual(simp("Bdim7"), "Bdim")
        self.assertEqual(simp("C#ø7"), "C#m")
        self.assertEqual(simp("A7sus4"), "A")  # suspension dropped
        self.assertEqual(simp("G13"), "G")  # dominant extension -> major triad
        self.assertEqual(simp("Am7/G"), "Am")  # slash bass dropped
        self.assertEqual(simp("G7", genre="Blues"), "G7")  # blues keeps the dominant seventh


class CatalogBeginnerChordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = list(curated_song_records())

    def test_every_beginner_chord_is_a_valid_symbol(self):
        bad = []
        for rec in self.records:
            _v, secs = resolve_level_chart(rec, "Beginner")
            for sec, bars in secs.items():
                for tok in bars:
                    for c in _chords(tok):
                        if is_no_chord_token(c):
                            continue
                        ok = bool(CHORD_RE.match(c))
                        if ok:
                            try:
                                ok = len(spell_chord_tones(c)) >= 3
                            except Exception:
                                ok = False
                        if not ok:
                            bad.append((rec["title"], sec, tok))
        self.assertEqual(bad, [])

    def test_beginner_events_validate_for_every_record(self):
        problems = []
        for rec in self.records:
            sig = rec.get("time_signature") or (rec.get("extensions") or {}).get("time_signature") or "4/4"
            _view, secs = resolve_level_chart(rec, "Beginner")
            ev = sections_dict_to_events(secs, time_signature=sig, section_order=list(secs))
            issues = validate_chord_events(ev, time_signature=sig)
            if issues:
                problems.append((rec["title"], issues[:2]))
        self.assertEqual(problems, [])

    def test_beginner_never_turns_minor_into_major(self):
        """A minor chord in the Advanced chart must stay minor (or diminished) at Beginner."""
        flips = []
        for rec in self.records:
            _v, adv = resolve_level_chart(rec, "Advanced")
            _v, beg = resolve_level_chart(rec, "Beginner")
            for sec, bars in beg.items():
                a = adv.get(sec)
                if not a or len(a) != len(bars):
                    continue
                for i, (b, x) in enumerate(zip(bars, a)):
                    pb, pa = parse_subdivisions(b), parse_subdivisions(x)
                    if not pb or not pa or is_no_chord_token(pa[0].chord):
                        continue
                    ra, fa = _family(pa[0].chord.removesuffix(".hit"))
                    rb, fb = _family(pb[0].chord.removesuffix(".hit"))
                    if ra == rb and fa == "min" and fb == "maj":
                        flips.append((rec["title"], sec, i, x, b))
        self.assertEqual(flips, [])


class CatalogIntermediateChordTests(unittest.TestCase):
    """Intermediate now plays the complete form, so every section's chords are reachable."""

    @classmethod
    def setUpClass(cls):
        cls.records = list(curated_song_records())

    def test_every_intermediate_chord_is_valid_and_events_validate(self):
        bad, issues = [], []
        for rec in self.records:
            sig = rec.get("time_signature") or (rec.get("extensions") or {}).get("time_signature") or "4/4"
            view, secs = resolve_level_chart(rec, "Intermediate")
            for sec, bars in secs.items():
                for tok in bars:
                    for c in _chords(tok):
                        if is_no_chord_token(c):
                            continue
                        ok = bool(CHORD_RE.match(c))
                        if ok:
                            try:
                                ok = len(spell_chord_tones(c)) >= 3
                            except Exception:
                                ok = False
                        if not ok:
                            bad.append((rec["title"], sec, tok))
            order = list(view.get("section_order") or secs)
            ev = sections_dict_to_events(secs, time_signature=sig, section_order=order)
            found = validate_chord_events(ev, time_signature=sig)
            if found:
                issues.append((rec["title"], found[:2]))
        self.assertEqual(bad, [])
        self.assertEqual(issues, [])

    def test_intermediate_never_turns_minor_into_major(self):
        flips = []
        for rec in self.records:
            _v, adv = resolve_level_chart(rec, "Advanced")
            _v, mid = resolve_level_chart(rec, "Intermediate")
            for sec, bars in mid.items():
                a = adv.get(sec)
                if not a or len(a) != len(bars):
                    continue
                for i, (b, x) in enumerate(zip(bars, a)):
                    pb, pa = parse_subdivisions(b), parse_subdivisions(x)
                    if not pb or not pa or is_no_chord_token(pa[0].chord):
                        continue
                    ra, fa = _family(pa[0].chord.removesuffix(".hit"))
                    rb, fb = _family(pb[0].chord.removesuffix(".hit"))
                    if ra == rb and fa == "min" and fb == "maj":
                        flips.append((rec["title"], sec, i, x, b))
        self.assertEqual(flips, [])


if __name__ == "__main__":
    unittest.main()


class SimplifiedChordEventsMatchTheSourceTiming(unittest.TestCase):
    """Generated chord events (what Backing and chord-follow consume), not just labels."""

    @classmethod
    def setUpClass(cls):
        cls.records = list(curated_song_records())

    def test_every_simplified_cell_keeps_its_sub_chord_count_weights_pushes_and_root(self):
        problems = []
        checked = 0
        for rec in self.records:
            if (rec.get("chart_versions") or {}).get("Beginner"):
                continue  # authored Beginner chart: not derived by the simplifier
            _v, adv = resolve_level_chart(rec, "Advanced")
            _v, beg = resolve_level_chart(rec, "Beginner")
            for sec, cells in beg.items():
                src = adv.get(sec)
                if not src or len(src) != len(cells):
                    continue
                for i, (b, a) in enumerate(zip(cells, src)):
                    pa, pb = parse_subdivisions(a), parse_subdivisions(b)
                    checked += 1
                    if len(pa) != len(pb):
                        problems.append((rec["title"], sec, i, a, b, "sub-chord count"))
                        continue
                    for x, y in zip(pa, pb):
                        if abs(x.weight - y.weight) > 1e-9 or bool(x.push) != bool(y.push):
                            problems.append((rec["title"], sec, i, a, b, "weight/push"))
                        if is_no_chord_token(x.chord) != is_no_chord_token(y.chord):
                            problems.append((rec["title"], sec, i, a, b, "N.C."))
                        elif not is_no_chord_token(x.chord):
                            rx = split_chord(x.chord.removesuffix(".hit").split("/")[0])[0]
                            ry = split_chord(y.chord.removesuffix(".hit").split("/")[0])[0]
                            if rx != ry:
                                problems.append((rec["title"], sec, i, a, b, "root"))
        self.assertGreater(checked, 100)
        self.assertEqual(problems, [])

    def test_beginner_chord_events_validate_for_every_catalog_song(self):
        for rec in self.records:
            view, secs = resolve_level_chart(rec, "Beginner")
            order = list(view.get("section_order") or secs)
            events = sections_dict_to_events({n: secs[n] for n in order})
            self.assertEqual(validate_chord_events(events), [], rec["title"])

    def test_only_how_far_ill_go_changes_its_visible_beginner_chords(self):
        # (dev 90b1b688 vs this branch: every other Beginner/Intermediate view is identical)
        rec = next(r for r in self.records if r["title"] == "How Far I'll Go")
        _v, adv = resolve_level_chart(rec, "Advanced")
        _v, beg = resolve_level_chart(rec, "Beginner")
        self.assertEqual(beg["Verse 1"][:4], ["E", "F#m", "C#m", "A"])
        self.assertEqual(adv["Verse 1"][:4], ["E", "F#m", "C#m", "A"])

    def test_backing_audio_of_a_simplified_song_has_the_expected_length(self):
        import io
        import wave

        from backing_audio import generate_backing_track
        from songs.meter import meter_timing

        rec = next(r for r in self.records if r["title"] == "How Far I'll Go")
        view, secs = resolve_level_chart(rec, "Beginner")
        order = list(view.get("section_order") or secs)
        chords = [c for n in order for c in secs[n]]
        ext = rec.get("extensions") or {}
        bpm = int(ext.get("default_bpm") or 100)
        wav = generate_backing_track(chords, bpm=bpm, loops=1, style=ext.get("default_groove") or "Pop groove",
                                     level="Beginner", song_title=rec["title"], song_artist=rec["artist"])
        with wave.open(io.BytesIO(wav)) as w:
            dur = w.getnframes() / w.getframerate()
        self.assertAlmostEqual(dur, len(chords) * meter_timing(bpm, "4/4").bar_sec + 1.0, delta=0.15)
