"""Songs-page card: personalized Harmony / Melody / Focus / Challenge per level × instrument × focus.

Guards against: mismatched instrument advice, generic focus text, harmony descriptions that
don't match the chart, invented melody facts, and key-mode guesses from a bare key label.
"""

from __future__ import annotations

import logging
import re
import unittest

from practice_setup_controls import DEFAULT_INSTRUMENT_OPTIONS, focus_options_for_instrument
from practice_studio import active_song_card_details
from song_card_guidance import (
    BEGINNER_FORBIDDEN,
    GENERATED_MELODY,
    MELODY_TOOL,
    analyze_song_harmony,
    build_song_card_guidance,
    expand_sections,
    focus_kind,
    instrument_family,
    key_label,
    key_token,
)

logging.disable(logging.CRITICAL)

LEVELS = ("Beginner", "Intermediate", "Advanced")
FIELDS = ("harmony", "melody", "focus", "challenge")
_RECS: dict = {}


# Several titles exist twice in the catalog (e.g. the "All of Me" jazz standard and John
# Legend's "All of Me"); the card must describe whichever record is active.
ARTISTS = {"All of Me": "John Legend", "Autumn Leaves": "Jazz Standard", "Satin Doll": "Duke Ellington",
           "Perfect": "Ed Sheeran", "Let It Be": "The Beatles"}


def song(title: str, artist: str | None = None) -> dict:
    if not _RECS:
        from song_catalog.catalog import bulk_song_records, curated_song_records

        for r in list(curated_song_records()) + list(bulk_song_records()):
            _RECS.setdefault((r["title"], r.get("artist")), r)
            _RECS.setdefault((r["title"], None), r)
    want = artist or ARTISTS.get(title)
    return _RECS.get((title, want)) or _RECS[(title, None)]


def card(title: str, level: str, instrument: str, focus: str, *, chart_key: str | None = None) -> dict:
    r = song(title)
    ext = r.get("extensions") or {}
    return build_song_card_guidance(
        r, level=level, instrument=instrument, focus=focus, practice_key=r["key"], chart_key=chart_key or r["key"],
        bpm=ext.get("default_bpm"), time_signature=ext.get("time_signature") or "4/4", groove=ext.get("default_groove") or "",
    )


def text_of(c: dict, *fields: str) -> str:
    return " ".join(c[f] for f in (fields or FIELDS))


# The requested acceptance matrix, with the real Practice Focus labels the app offers
# for each instrument (Guitar has "Rhythm Guitar", Voice has "Breath Control").
MATRIX = [
    ("Satin Doll", "Beginner", "Saxophone", "Tone"),
    ("Satin Doll", "Intermediate", "Saxophone", "Guide Tones"),
    ("Satin Doll", "Advanced", "Saxophone", "Bebop Phrasing"),
    ("Satin Doll", "Advanced", "Piano", "Guide Tones"),
    ("Satin Doll", "Advanced", "Piano", "Voice Leading"),
    ("Satin Doll", "Intermediate", "Guitar", "Rhythm Guitar"),
    ("Perfect", "Beginner", "Guitar", "Strumming"),
    ("Perfect", "Intermediate", "Voice", "Breath Control"),
    ("All of Me", "Advanced", "Piano", "Pentatonics"),
    ("Twist and Shout", "Beginner", "Piano", "Voicings"),
    ("Let It Be", "Intermediate", "Bass", "Walking Bass"),
]


class TestSetupAndFocusAreTheUsers(unittest.TestCase):
    def test_setup_and_focus_label_show_the_selected_values(self) -> None:
        for title, level, inst, focus in MATRIX:
            c = card(title, level, inst, focus)
            self.assertEqual(c["setup"], f"{level} · {inst} · {focus}")
            self.assertEqual(c["focus_label"], focus)
            for f in FIELDS:
                self.assertTrue(c[f].strip(), (title, level, inst, focus, f))

    def test_focus_changes_focus_and_challenge_not_the_song_facts(self) -> None:
        cards = {f: card("Satin Doll", "Intermediate", "Saxophone", f) for f in focus_options_for_instrument("Saxophone")}
        self.assertEqual(len({c["focus"] for c in cards.values()}), len(cards), "each focus gets its own guidance")
        self.assertEqual(len({c["challenge"] for c in cards.values()}), len(cards), "each focus gets its own challenge")
        self.assertEqual(len({c["harmony"] for c in cards.values()}), 1, "harmony facts don't depend on focus")

    def test_focus_text_is_about_the_focus(self) -> None:
        expect = {
            "Guide Tones": r"3rds? and (the )?7ths?|guide-tone",
            "Pentatonics": r"pentatonic",
            "Tone": r"tone|sound",
            "Breath Support": r"breath",
            "Articulation": r"tongu|slur|articulation",
            "Bebop Phrasing": r"eighth|chromatic|enclos|bebop",
            "Scales": r"scale",
            "Dynamics": r"soft|loud|dynamic|crescendo",
        }
        for focus, pat in expect.items():
            for level in LEVELS:
                c = card("Satin Doll", level, "Saxophone", focus)
                self.assertRegex(c["focus"].lower(), pat, (focus, level, c["focus"]))

    def test_unknown_or_cross_instrument_focus_still_gets_specific_guidance(self) -> None:
        for focus in ("Guide Tones", "Rhythm", "Melody", "Technique", "Harmony"):
            c = card("Satin Doll", "Intermediate", "Piano", focus)
            self.assertTrue(c["focus"] and c["challenge"])
        self.assertEqual(focus_kind("Rhythm Guitar"), "rhythm")
        self.assertEqual(focus_kind("Breath Control"), "breath")
        self.assertEqual(focus_kind("Voice Leading"), "voice_leading")


class TestLevelLanguage(unittest.TestCase):
    def test_beginner_cards_avoid_advanced_jargon(self) -> None:
        for title in ("Satin Doll", "All of Me", "Perfect", "Autumn Leaves", "Twist and Shout"):
            for inst in ("Piano", "Guitar", "Saxophone", "Voice", "Bass", "Trumpet"):
                for focus in focus_options_for_instrument(inst):
                    low = text_of(card(title, "Beginner", inst, focus)).lower()
                    for word in BEGINNER_FORBIDDEN:
                        self.assertNotIn(word, low, (title, inst, focus))

    def test_advanced_is_more_sophisticated_not_just_longer(self) -> None:
        beg = card("Satin Doll", "Beginner", "Saxophone", "Guide Tones")
        adv = card("Satin Doll", "Advanced", "Saxophone", "Guide Tones")
        self.assertRegex(text_of(adv, "harmony").lower(), r"ii–v|tonicizing|chromatic")
        self.assertRegex(text_of(adv, "focus", "challenge").lower(), r"chromatic|continuous")
        for f in FIELDS:
            self.assertNotEqual(beg[f], adv[f])

    def test_the_success_criterion(self) -> None:
        a = card("Satin Doll", "Beginner", "Saxophone", "Tone")
        b = card("Satin Doll", "Advanced", "Piano", "Guide Tones")
        for f in FIELDS:
            self.assertNotEqual(a[f], b[f], f)
        self.assertIn("long tones", a["focus"])
        self.assertIn("voicings", b["focus"])
        self.assertIn("C major", a["harmony"])
        self.assertIn("C major", b["harmony"])


class TestInstrumentAppropriateness(unittest.TestCase):
    FORBID = {
        "guitar": (r"\bstrum", r"\bfret(?!ting-hand)", r"\bpick(ing|ed)?\b", r"\bbarre\b", r"\bcapo\b"),
        "piano": (r"left[- ]hand", r"right[- ]hand", r"\bpedal\b"),
        "wind": (r"\btongu", r"embouchure"),
    }

    def test_no_instrument_gets_another_instruments_technique(self) -> None:
        for inst in DEFAULT_INSTRUMENT_OPTIONS:
            fam = instrument_family(inst)
            for focus in focus_options_for_instrument(inst):
                for level in LEVELS:
                    for title in ("Satin Doll", "Perfect", "All of Me"):
                        low = text_of(card(title, level, inst, focus), "focus", "challenge").lower()
                        pats = []
                        if fam != "guitar":
                            # Basses are fretted too; strumming, picks, barre chords and capos stay guitar-only.
                            pats += [p for p in self.FORBID["guitar"] if not (fam == "bass" and "fret" in p)]
                        if fam != "piano":
                            pats += self.FORBID["piano"]
                        if fam not in ("sax", "brass", "flute", "clarinet"):
                            pats += self.FORBID["wind"]
                        for pat in pats:
                            self.assertNotRegex(low, pat, (inst, focus, level, title))

    def test_saxophone_never_gets_strumming_and_guitar_gets_guitar_language(self) -> None:
        sax = text_of(card("Satin Doll", "Intermediate", "Saxophone", "Articulation")).lower()
        self.assertNotIn("strum", sax)
        self.assertRegex(sax, r"tongu|slur")
        gtr = text_of(card("Perfect", "Beginner", "Guitar", "Strumming")).lower()
        self.assertIn("strum", gtr)
        piano = card("Satin Doll", "Intermediate", "Piano", "Voicings")["focus"].lower()
        self.assertIn("left-hand", piano)

    def test_instrument_families(self) -> None:
        self.assertEqual(
            [instrument_family(i) for i in ("Piano", "Guitar", "Bass", "Alto Sax", "Trumpet", "Flute", "Clarinet", "Voice", "Other")],
            ["piano", "guitar", "bass", "sax", "brass", "flute", "clarinet", "voice", "other"],
        )
        self.assertEqual(instrument_family("Bass Guitar"), "bass")


class TestHarmonyMatchesTheChart(unittest.TestCase):
    def test_pipe_bars_are_expanded(self) -> None:
        rows = expand_sections({"A": ["Dm7|G7", "Cmaj7"]})
        self.assertEqual(rows, [("A", ["Dm7", "G7", "Cmaj7"])])

    def test_satin_doll_is_ii_v_harmony_with_an_f_bridge(self) -> None:
        f = analyze_song_harmony(song("Satin Doll"))
        self.assertEqual(f.character, "functional")
        pairs = {(a, b) for a, b, _t, _r in f.ii_v}
        self.assertTrue({("Dm7", "G7"), ("Em7", "A7"), ("Am7", "D7"), ("Gm7", "C7")} <= pairs)
        self.assertIn(("Fmaj7", "IV", "B (Bridge)"), f.tonicized)
        self.assertIn(["B7", "Bb7", "A7"], f.chromatic_dominants)
        self.assertIn("ii–V", (f.verified_summary or "ii–V").replace("-", "–"))  # agrees with verified metadata
        inter = card("Satin Doll", "Intermediate", "Saxophone", "Guide Tones")["harmony"]
        self.assertIn("ii–V", inter)
        self.assertIn("Fmaj7", inter)

    def test_all_of_me_is_a_minor_loop_not_a_jazz_standard(self) -> None:
        f = analyze_song_harmony(song("All of Me"))
        self.assertEqual(f.character, "loop")
        self.assertEqual(f.loop, ("Em", "C", "G", "D"))
        self.assertEqual(f.loop_numerals, ("i", "VI", "III", "VII"))
        for level in LEVELS:
            c = card("All of Me", level, "Piano", "Pentatonics")
            low = c["harmony"].lower()
            self.assertIn("e minor", low) if level != "Beginner" else self.assertIn("em", low)
            self.assertNotRegex(text_of(c).lower(), r"ii–v|turnaround|swing|bridge modulation")

    def test_all_of_me_jazz_standard_is_a_secondary_dominant_chain(self) -> None:
        r = song("All of Me", "Jazz Standard")
        f = analyze_song_harmony(r)
        self.assertEqual(f.character, "functional")
        self.assertEqual(f.dominant_chains()[0], ["E7", "A7", "Dm7"])
        self.assertEqual(f.secondary_labels["E7"], "V/vi")
        c = build_song_card_guidance(r, level="Advanced", instrument="Piano", focus="Pentatonics", practice_key="C", chart_key="C")
        self.assertIn("E7 → A7 → Dm7", c["harmony"])
        self.assertIn("V/vi", c["harmony"])
        self.assertNotIn("unresolved", c["harmony"])  # Am7–D7 does land on G7

    def test_simple_diatonic_song_is_described_simply(self) -> None:
        f = analyze_song_harmony(song("Twist and Shout"))
        self.assertEqual(f.character, "diatonic")
        self.assertEqual(sorted(f.distinct), ["A", "D", "G"])
        for level in LEVELS:
            h = card("Twist and Shout", level, "Guitar", "Strumming")["harmony"]
            self.assertIn("D major", h)
            self.assertNotRegex(h.lower(), r"ii–v|secondary|chromatic|tritone")

    def test_harmony_facts_do_not_change_with_level_only_language_does(self) -> None:
        for title in ("Satin Doll", "Perfect", "Let It Be"):
            texts = {level: card(title, level, "Piano", "Voicings")["harmony"] for level in LEVELS}
            self.assertEqual(len(set(texts.values())), 3, title)
        f1 = analyze_song_harmony(song("Satin Doll"))
        f2 = analyze_song_harmony(song("Satin Doll"))
        self.assertEqual((f1.character, f1.ii_v, f1.tonicized), (f2.character, f2.ii_v, f2.tonicized))

    def test_no_swing_claims_for_songs_that_do_not_swing(self) -> None:
        for title in ("Perfect", "All of Me", "Let It Be", "Twist and Shout"):
            groove = str((song(title).get("extensions") or {}).get("default_groove") or "").lower()
            self.assertNotIn("swing", groove)
            for inst in ("Saxophone", "Piano", "Guitar"):
                for focus in focus_options_for_instrument(inst):
                    for level in LEVELS:
                        self.assertNotIn("swing", text_of(card(title, level, inst, focus)).lower(), (title, inst, focus))

    def test_meter_is_respected(self) -> None:
        c = card("Perfect", "Beginner", "Guitar", "Strumming")
        self.assertIn("two down-strums per bar", c["challenge"])
        self.assertNotIn("four strums", c["challenge"])


class TestMelodyIsHonest(unittest.TestCase):
    def test_melody_points_to_generated_practice_melody_and_never_claims_the_original(self) -> None:
        for title, level, inst, focus in MATRIX:
            m = card(title, level, inst, focus)["melody"]
            self.assertIn(GENERATED_MELODY, m)
            self.assertIn("Practice page", m)
            self.assertIn(MELODY_TOOL, m)
            self.assertIn("not the original melody", m)
            self.assertNotRegex(m.lower(), r"(the|its) (original|real) melody (is|goes|starts|uses)")
            # No invented note sequences (three or more note names chained by dashes).
            self.assertNotRegex(m, r"\b[A-G][♭♯#b]?\s*[–-]\s*[A-G][♭♯#b]?\s*[–-]\s*[A-G]\b")

    def test_no_catalog_song_carries_verified_melody_data(self) -> None:
        # If this ever changes, the Melody field may start describing real melodies.
        r = song("Satin Doll")
        self.assertFalse(r.get("melody") or (r.get("extensions") or {}).get("melody"))

    def test_melody_language_follows_level_and_instrument(self) -> None:
        beg = card("Perfect", "Beginner", "Voice", "Phrasing")["melody"]
        adv = card("Perfect", "Advanced", "Piano", "Voicings")["melody"]
        self.assertTrue(beg.startswith("Sing"))
        self.assertIn("motif", adv)
        self.assertNotIn("motif", beg)


class TestKeysAndTransposition(unittest.TestCase):
    def test_mode_comes_from_the_song_when_the_label_omits_it(self) -> None:
        self.assertEqual(key_token("G", "Em"), "Gm")
        self.assertEqual(key_token("E", "C"), "E")
        self.assertEqual(key_token("Ebm", "C"), "Ebm")
        self.assertEqual(key_label("Gm"), "G minor")
        d = active_song_card_details(song("All of Me"), level="Beginner", instrument="Piano", practice_key="G", chart_key="G")
        self.assertEqual(d["key_display"], "G minor")

    def test_written_key_spelling_for_transposing_instruments(self) -> None:
        d = active_song_card_details(
            song("Satin Doll"), level="Intermediate", instrument="Alto Sax", practice_key="C", chart_key="A", focus="Guide Tones"
        )
        g = d["card_guidance"]
        self.assertIn("Bm7–E7", g["harmony"])
        self.assertIn("A major", g["harmony"])
        self.assertIn("Dmaj7", g["harmony"])
        self.assertIn("sounds in C major", g["key_mode_label"])
        self.assertNotIn("Dm7", g["harmony"])


def _chart_key(session: dict, concert: str) -> str:
    """The chart key the rest of the app shows for this session (written / shape / concert)."""
    from effective_practice_context import musician_facing_chart_key

    return musician_facing_chart_key(dict(session), concert)


ALTO = "Alto saxophone (Eb)"
TENOR = "Tenor saxophone (Bb)"


def _sax(sax_type: str, written: bool) -> dict:
    return {"instrument": "Saxophone", "saxophone_type": sax_type, "selected_transposing_instrument": sax_type,
            "show_chart_in_instrument_key": written}


def _guitar(shape: str | None) -> dict:
    return {"instrument": "Guitar", "guitar_capo_enabled": bool(shape), "guitar_capo_shape_key": shape or ""}


class TestKeyDisplayModes(unittest.TestCase):
    """Card chords follow the app's Concert / Written / Shape projection; the harmony itself never changes."""

    def _card(self, title, session, practice, *, level="Intermediate", focus="", mode="concert", t_type="", capo=None):
        rec = song(title)
        chart = _chart_key(session, practice)
        return build_song_card_guidance(rec, level=level, instrument=session["instrument"], focus=focus,
                                        practice_key=practice, chart_key=chart, key_mode=mode,
                                        transposing_type=t_type, capo_fret=capo)

    def test_concert_mode_spells_concert_chords_and_says_so(self) -> None:
        g = self._card("Satin Doll", {"instrument": "Piano"}, "C", focus="Voice Leading")
        self.assertEqual(g["key_mode"], "concert")
        self.assertIn("Dm7–G7", g["harmony"])
        self.assertTrue(g["key_mode_label"].startswith("Concert key · C major"))

    def test_practice_concert_key_change_moves_every_section(self) -> None:
        g = self._card("Satin Doll", {"instrument": "Piano"}, "Eb", focus="Guide Tones")
        self.assertIn("Fm7–B♭7", g["harmony"])
        self.assertIn("E♭ major", g["harmony"])
        self.assertIn("Fm7–B♭7", g["challenge"])
        self.assertIn("E♭ → D", g["focus"])  # 7th of Fm7 → 3rd of B♭7
        for field in ("harmony", "focus", "challenge"):
            self.assertNotIn("Dm7", g[field])
            self.assertNotIn("G7", g[field])
        self.assertIn("E♭ major", g["key_mode_label"])

    def test_alto_sax_written_mode(self) -> None:
        session = _sax(ALTO, True)
        self.assertEqual(_chart_key(session, "C"), "A")
        g = self._card("Satin Doll", session, "C", focus="Guide Tones", mode="written", t_type=ALTO)
        self.assertEqual(g["key_mode"], "written")
        self.assertEqual(g["chart_key"], "A")
        self.assertIn("Bm7–E7", g["harmony"])
        self.assertIn("A major", g["harmony"])
        self.assertIn("Bm7–E7", g["challenge"])
        self.assertIn("A → G♯", g["focus"])  # written 7th of Bm7 → 3rd of E7 (concert C → B)
        for field in ("harmony", "focus", "challenge"):
            self.assertNotIn("Dm7", g[field])
        self.assertIn("Written key · A major for Alto saxophone (Eb)", g["key_mode_label"])
        self.assertIn("sounds in C major", g["key_mode_label"])

    def test_tenor_sax_written_mode(self) -> None:
        session = _sax(TENOR, True)
        self.assertEqual(_chart_key(session, "C"), "D")
        g = self._card("Satin Doll", session, "C", focus="Guide Tones", mode="written", t_type=TENOR)
        self.assertIn("Em7–A7", g["harmony"])
        self.assertIn("Written key · D major for Tenor saxophone (Bb)", g["key_mode_label"])

    def test_sax_with_written_key_off_stays_in_concert(self) -> None:
        session = _sax(ALTO, False)
        self.assertEqual(_chart_key(session, "C"), "C")
        g = self._card("Satin Doll", session, "C", focus="Guide Tones", mode="concert", t_type=ALTO)
        self.assertIn("Dm7–G7", g["harmony"])
        self.assertTrue(g["key_mode_label"].startswith("Concert key"))

    def test_guitar_capo_shape_mode(self) -> None:
        from guitar_capo import capo_fret_for_shape

        session = _guitar("G")
        self.assertEqual(_chart_key(session, "A"), "G")
        capo = capo_fret_for_shape("A", "G")
        self.assertEqual(capo, 2)
        g = self._card("Satin Doll", session, "A", focus="Rhythm Guitar", mode="shape", capo=capo)
        self.assertEqual(g["key_mode"], "shape")
        self.assertIn("Am7–D7", g["harmony"])  # concert Bm7–E7 in A, gripped as G shapes
        self.assertIn("G major", g["harmony"])
        self.assertNotIn("C♯m7", g["harmony"])  # concert ii of A must not leak into the shape chart
        self.assertIn("Shape key · G major shapes, capo 2", g["key_mode_label"])
        self.assertIn("sounds in A major", g["key_mode_label"])

    def test_guitar_shape_mode_keeps_minor_songs_minor(self) -> None:
        rec = song("Autumn Leaves")
        practice = key_token(rec["key"], rec["key"])
        self.assertTrue(practice.endswith("m"))
        session = _guitar("E")
        chart = _chart_key(session, practice)
        self.assertEqual(chart, "Em")
        from guitar_capo import capo_fret_for_shape

        g = self._card("Autumn Leaves", session, practice, mode="shape", capo=capo_fret_for_shape(practice, "E"))
        self.assertIn("E minor shapes", g["key_mode_label"])
        self.assertIn("E minor", g["harmony"])

    def test_guitar_without_capo_is_concert(self) -> None:
        session = _guitar(None)
        self.assertEqual(_chart_key(session, "A"), "A")
        g = self._card("Satin Doll", session, "A", focus="Rhythm Guitar")
        self.assertIn("Bm7–E7", g["harmony"])
        self.assertTrue(g["key_mode_label"].startswith("Concert key · A major"))

    def test_modes_never_change_the_canonical_harmony(self) -> None:
        import copy

        rec = song("Satin Doll")
        before = copy.deepcopy(rec)
        cards = [
            self._card("Satin Doll", {"instrument": "Piano"}, "C"),
            self._card("Satin Doll", _sax(ALTO, True), "C", mode="written", t_type=ALTO),
            self._card("Satin Doll", _guitar("G"), "A", mode="shape", capo=2),
        ]
        self.assertEqual(rec, before)
        facts = [c["facts"] for c in cards]
        self.assertTrue(all(f.ii_v == facts[0].ii_v for f in facts))
        self.assertTrue(all(f.form == facts[0].form for f in facts))
        plain = build_song_card_guidance(rec, level="Intermediate", instrument="Piano", focus="")
        self.assertEqual(plain["harmony"], cards[0]["harmony"])

    def test_mode_falls_back_to_concert_when_chart_equals_concert(self) -> None:
        g = build_song_card_guidance(song("Satin Doll"), level="Beginner", instrument="Saxophone", focus="",
                                     practice_key="C", chart_key="C", key_mode="written", transposing_type=ALTO)
        self.assertEqual(g["key_mode"], "concert")
        self.assertTrue(g["key_mode_label"].startswith("Concert key"))

    def test_capo_shape_mode_with_shapes_at_sounding_pitch_says_no_capo(self) -> None:
        g = self._card("Perfect", _guitar("G"), "G", mode="shape", capo=0)
        self.assertEqual(g["key_mode"], "shape")
        self.assertIn("Shape key · G major shapes, no capo", g["key_mode_label"])

    def test_melody_stays_a_pointer_in_every_mode(self) -> None:
        for g in (
            self._card("Satin Doll", _sax(ALTO, True), "C", mode="written", t_type=ALTO),
            self._card("Satin Doll", _guitar("G"), "A", mode="shape", capo=2),
        ):
            self.assertIn(GENERATED_MELODY, g["melody"])
            self.assertIn("not the original melody", g["melody"])


class TestCardDetailsAndHtml(unittest.TestCase):
    def test_details_carry_guidance_and_keep_legacy_fields(self) -> None:
        d = active_song_card_details(song("Satin Doll"), level="Advanced", instrument="Piano", practice_key="C", chart_key="C",
                                     focus="Voice Leading")
        for key in ("levels_display", "instruments", "practice_focus", "bpm", "time_signature", "key_display", "section_summary"):
            self.assertIn(key, d)
        g = d["card_guidance"]
        self.assertEqual(g["setup"], "Advanced · Piano · Voice Leading")
        self.assertEqual(g["form"], "AABA (32 bars) + Turnaround (4 bars)")

    def test_card_html_shows_setup_and_the_four_guidance_rows(self) -> None:
        import ast
        import html as html_mod
        from pathlib import Path

        src = Path(__file__).resolve().parents[1].joinpath("streamlit_music_practice_app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_song_card_guidance_html")
        ns: dict = {"html": html_mod}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "card", "exec"), ns)
        d = active_song_card_details(song("Satin Doll"), level="Intermediate", instrument="Saxophone", practice_key="C",
                                     chart_key="C", focus="Guide Tones")
        out = ns["_song_card_guidance_html"](d)
        for label in ("Your setup", "Form", "Chart levels", "Common instruments", "Harmony:", "Melody:",
                      "Your focus — Guide Tones:", "Your challenge:"):
            self.assertIn(label, out)
        self.assertNotIn("Level fit", out)
        self.assertNotIn("Let the harmony support the melody", out)
        self.assertEqual(len(re.findall(r'class="ui-active-song-blurb ui-song-guide"', out)), 4)
        self.assertIn("Key shown:</strong> Concert key · C major", out)
        legacy = ns["_song_card_guidance_html"]({**d, "card_guidance": {}})
        self.assertIn("Practice focus", legacy)

    def test_custom_progression_without_metadata_still_works(self) -> None:
        rec = {"title": "My progression", "key": "G", "sections": {"Verse": ["G", "C", "D", "G"]}}
        c = build_song_card_guidance(rec, level="Beginner", instrument="Guitar", focus="Strumming", practice_key="G")
        self.assertIn("G major", c["harmony"])
        empty = build_song_card_guidance({"title": "Empty", "key": "C", "sections": {}}, level="Beginner",
                                         instrument="Piano", focus="Voicings")
        self.assertIn("chord chart", empty["harmony"])


if __name__ == "__main__":
    unittest.main()
