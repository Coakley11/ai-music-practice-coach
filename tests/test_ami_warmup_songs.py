"""Adaptive warmups, Slice 2a: song-aware guide-tone preparation over the active song's chart.

Independent verification: ``tests/song_oracle.py`` has its own chord reader and ABC tokenizer. Every written note of every generated line is checked against
the third / seventh (or sixth) of the CHARTED chord at that beat, in sounding pitch (written − the instrument's exact offset), on real catalog songs.
"""
from __future__ import annotations

import copy
import re
from fractions import Fraction

import pytest

from music_coach_ami import warmup_engine as we
from music_coach_ami import warmup_plan as wp
from music_coach_ami import warmup_song as ws
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.pipeline import run_coach_submit
from tests import song_oracle as oracle
from tests.song_fixtures import ALTO, TENOR, activate_song, lib_song, song_session
from tests.test_abc_bar_accidentals import read_abc

OFFSET = {"flute": 0, "piano": 0, "alto": 9, "tenor": 14, "soprano": 2, "trumpet": 2, "clarinet": 2, "baritone": 21}


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


def ctx(instrument="Saxophone", level="Intermediate", key="Cm"):
    return {"instrument": instrument, "level": level, "focus": "Improvisation", "display_key": key, "bpm": 100}


def ask(s, q, **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(**kw))[1]


def plan_of(s):
    p = wp.current(s)
    assert p is not None, "no active warmup"
    return p


def build_tune(who, title, section, level, *, tones="both", first="auto", style="steady", bars=None, smooth=False, key=None):
    song = lib_song(title, key=key)
    pl = we.make_player(who, song["practice_key"])
    built = ws.build(pl, level, song, section, bars, tones=tones, first=first, style=style, smooth=smooth)
    tonic, tonality = we.practical_key(*we.split_key(pl.written_key))
    abc, diag = we.render(pl, built, tonic, tonality, title=built.title, bpm=built.bpm)
    checks = ws.verify(pl, level, built, diag)
    return pl, built, abc, checks, song


# ================================================================ 1. the independent oracle on real songs, every instrument, level and variant

SONGS = [("Blue Bossa", ["Section A", "Section B", "Head"]), ("Autumn Leaves", ["A Section", "C Section"]), ("Satin Doll", ["A", "B (Bridge)"]),
         ("Take the A Train", ["A Section"]), ("The Girl from Ipanema", ["B Section"]), ("All the Things You Are", ["A", "Bridge", "A3"])]
INSTRUMENTS = ["flute", "alto", "tenor", "soprano", "baritone", "clarinet", "trumpet", "piano"]


@pytest.mark.parametrize("who", INSTRUMENTS)
def test_every_note_is_a_guide_tone_of_the_charted_chord_at_its_beat(who):
    n = 0
    for title, sections in SONGS:
        for section in sections:
            for level in we.LEVELS:
                for tones, first, style in ws.VARIANTS[level]:
                    pl, built, abc, checks, song = build_tune(who, title, section, level, tones=tones, first=first, style=style)
                    problems = oracle.check_tune(abc, song["sections"][section], pl.offset)
                    assert not problems, (who, title, section, level, tones, first, style, problems[:3])
                    assert pl.offset == OFFSET[who] and all(c["ok"] for c in checks)
                    n += 1
    assert n >= 140


class TestTheOracleCatchesWrongMusic:
    """The oracle must fail on deliberately wrong tunes, otherwise 'no problems' would mean nothing."""

    def setup_method(self):
        self.pl, self.built, self.abc, _c, self.song = build_tune("alto", "Blue Bossa", "Section A", "Intermediate")
        self.slots = self.song["sections"]["Section A"]
        head, self.body = self.abc.split("K:", 1)
        self.head = head + "K:"

    def test_the_unmodified_tune_passes(self):
        assert oracle.check_tune(self.abc, self.slots, self.pl.offset) == []

    def test_a_note_moved_by_a_semitone_is_caught(self):
        body = re.sub(r"(\"[^\"]+\")([a-gA-G])", r"\1^\2", self.body, count=1)
        assert body != self.body
        assert oracle.check_tune(self.head + body, self.slots, self.pl.offset)

    def test_the_wrong_instrument_offset_is_caught(self):
        assert oracle.check_tune(self.abc, self.slots, self.pl.offset + 2)

    def test_a_missing_chord_symbol_is_caught(self):
        body = re.sub(r'"[^"]*"', "", self.body, count=1)
        assert any("no chord symbol" in p for p in oracle.check_tune(self.head + body, self.slots, self.pl.offset))

    def test_a_chart_with_a_different_chord_is_caught(self):
        other = list(self.slots)
        other[4] = "Gm7"
        assert oracle.check_tune(self.abc, other, self.pl.offset)

    def test_a_shifted_chord_change_is_caught(self):
        body = self.body.replace("| ", "", 1)                       # one bar line less: the notes still sum, but the timeline is the same -> still passes
        assert oracle.check_tune(self.head + body, self.slots[:-1], self.pl.offset)     # a chart one bar shorter must not match


# ================================================================ 2. chord spelling, qualities and enharmonics

CHORDS = [  # symbol, kind of result: (concert third, concert seventh/sixth)
    ("Cmaj7", ("E", "B")), ("Cm7", ("Eb", "Bb")), ("C7", ("E", "Bb")), ("Cm7b5", ("Eb", "Bb")), ("CmMaj7", ("Eb", "B")), ("C7#5", ("E", "Bb")), ("C9", ("E", "Bb")),
    ("Cm9", ("Eb", "Bb")), ("Cmaj9", ("E", "B")), ("C13", ("E", "Bb")), ("C7b9", ("E", "Bb")), ("C6", ("E", "A")), ("Cm6", ("Eb", "A")), ("Ab7", ("C", "Gb")),
    ("F#m7", ("A", "E")), ("Db7", ("F", "Cb")), ("G#m7b5", ("B", "F#")), ("Bbmaj7", ("D", "A")), ("Ebm7", ("Gb", "Db")), ("C", ("E", None)), ("Am", ("C", None)),
]


@pytest.mark.parametrize("symbol,expected", CHORDS)
def test_concert_thirds_and_sevenths_are_spelled_for_the_chord(symbol, expected):
    info = ws.chord_info(symbol, 0, 0)
    assert info["ok"], info
    assert (info["concert"]["third"], info["concert"]["upper"]) == expected


@pytest.mark.parametrize("who", ["alto", "tenor", "flute", "soprano", "baritone"])
@pytest.mark.parametrize("symbol,expected", CHORDS)
def test_written_tones_never_need_a_double_accidental_and_keep_the_chord_quality(who, symbol, expected):
    pl = we.make_player(who, "Cm")
    info = ws.chord_info(symbol, pl.offset, pl.semitones)
    assert info["ok"], (who, symbol, info)
    t = oracle.chord_tones(symbol)
    w = info["written"]
    for name in (w["root"], w["third"], w["upper"]):
        assert name is None or not re.search(r"(##|bb)", name), (who, symbol, w)
    assert oracle.note_pc(w["third"]) == (t[0] + pl.offset) % 12
    if t[1] is not None or t[2] is not None:
        assert oracle.note_pc(w["upper"]) == ((t[1] if t[1] is not None else t[2]) + pl.offset) % 12


def test_known_written_spellings():
    alto = we.make_player("alto", "Cm")           # concert + 9 semitones
    assert ws.chord_info("Ab7", alto.offset, alto.semitones)["written"] == {"root": "F", "third": "A", "upper": "Eb"}
    assert ws.chord_info("F#m7", alto.offset, alto.semitones)["written"] == {"root": "D#", "third": "F#", "upper": "C#"}
    tenor = we.make_player("tenor", "Cm")          # concert + 14
    assert ws.chord_info("Ab7", tenor.offset, tenor.semitones)["written"] == {"root": "Bb", "third": "D", "upper": "Ab"}
    flute = we.make_player("flute", "Cm")
    assert ws.chord_info("Ab7", flute.offset, flute.semitones)["written"] == {"root": "Ab", "third": "C", "upper": "Gb"}


@pytest.mark.parametrize("symbol,why", [("Csus4", "no third"), ("Cdim7", "diminished"), ("N.C.", "not a chord"), ("Bdim", "diminished")])
def test_chords_that_cannot_be_written_are_named_not_guessed(symbol, why):
    info = ws.chord_info(symbol, 0, 0)
    assert not info["ok"] and why.split()[-1] in info["reason"].lower()


def test_triads_and_sixth_chords_say_what_stands_in_for_the_seventh():
    assert "only its third" in ws.chord_info("Am", 0, 0)["note"]
    assert "sixth" in ws.chord_info("C6", 0, 0)["note"]
    assert ws.chord_info("Am", 0, 0)["upper_role"] == ""


def test_a_slash_chord_uses_the_chord_above_the_bass():
    info = ws.chord_info("C/E", 0, 0)
    assert info["ok"] and info["concert"]["third"] == "E" and info["slash_bass"]


# ================================================================ 3. timeline, split measures, unsupported passages


class TestSplitMeasures:
    def test_satin_doll_two_chords_in_a_bar_each_get_two_beats_on_their_own_beat(self):
        pl, built, abc, _c, song = build_tune("flute", "Satin Doll", "A", "Intermediate")
        tune = oracle.read_tune(abc)
        for bar in range(4):
            first = [t for t in tune if t[0] == 4 * bar][0]
            second = [t for t in tune if t[0] == 4 * bar + 2][0]
            assert first[3] != second[3] and first[3] and second[3]
        assert [s["beats"] for s in built.meta["segments"]][:4] == [2.0, 2.0, 2.0, 2.0]
        assert sum(t[1] for t in tune) == 32

    def test_every_chord_change_starts_a_note_exactly_on_its_beat(self):
        for who in ("flute", "tenor"):
            pl, built, abc, _c, song = build_tune(who, "Satin Doll", "B (Bridge)", "Advanced", tones="both", first="auto", style="cells")
            assert oracle.check_tune(abc, song["sections"]["B (Bridge)"], pl.offset) == []

    def test_a_three_one_split_and_a_single_chord_bar_are_timed_by_their_beats(self):
        song = lib_song("Blue Bossa")
        song["sections"]["X"] = ["Cm7:3|G7:1", "Fm7"]
        song["order"].append("X")
        pl = we.make_player("flute", "Cm")
        built = ws.build(pl, "Intermediate", song, "X", None, tones="both", first="auto", style="steady")
        assert [s["beats"] for s in built.meta["segments"]] == [3.0, 1.0, 4.0]
        tonic, tonality = we.practical_key(*we.split_key(pl.written_key))
        abc, _ = we.render(pl, built, tonic, tonality, title="t", bpm=72)
        tune = oracle.read_tune(abc)
        assert [t[0] for t in tune if t[3]][:3] == [0, 3, 4] or {Fraction(0), Fraction(3), Fraction(4)} <= {t[0] for t in tune}


class TestUnsupportedChords:
    def test_a_diminished_chord_is_rested_for_exactly_its_time_and_named(self):
        pl, built, abc, _c, song = build_tune("tenor", "All the Things You Are", "A3", "Intermediate")
        bars = [(u["bar"], u["concert"]) for u in built.meta["unsupported"]]
        assert bars == [(8, "Bdim7")]
        tune = oracle.read_tune(abc)
        bar8 = [t for t in tune if 28 <= t[0] < 32]
        assert bar8 and all(t[2] is None for t in bar8) and sum(t[1] for t in bar8) == 4
        assert bar8[0][3]                                                  # the chord symbol is still shown over the rest
        assert oracle.check_tune(abc, song["sections"]["A3"], pl.offset) == []
        assert any("Rests mark chords" in x and "Bdim7" in x and "bar 8" in x for x in built.listen)

    def test_the_other_bars_keep_their_original_beat_positions(self):
        pl, built, abc, _c, song = build_tune("alto", "All the Things You Are", "A3", "Advanced", style="cells")
        starts = {t[0] for t in oracle.read_tune(abc)}
        assert {Fraction(4 * i) for i in range(12)} <= starts

    def test_a_section_that_is_mostly_unsupported_is_refused_not_guessed(self):
        song = lib_song("Blue Bossa")
        song["sections"]["Sus"] = ["Csus4", "Gsus4", "Dsus4", "Cm7"]
        song["order"].append("Sus")
        pl = we.make_player("flute", "Cm")
        with pytest.raises(ws.SongUnavailable) as e:
            ws.build(pl, "Intermediate", song, "Sus", None, tones="both", first="auto", style="steady")
        assert "Csus4" in str(e.value) and "bar" not in "" and "trustworthy" in str(e.value)

    def test_a_triad_gets_its_third_and_is_flagged(self):
        pl, built, abc, _c, song = build_tune("flute", "Autumn Leaves", "A Section", "Intermediate")
        flagged = [p for p in built.meta["segments"] if p.get("note")]
        assert any(p["concert"] == "Bm" for p in flagged) and "only its third" in flagged[0]["note"]
        assert oracle.check_tune(abc, song["sections"]["A Section"], pl.offset) == []

    def test_only_the_charts_own_bars_are_used_for_a_section_that_does_not_exist(self):
        song = lib_song("Blue Bossa")
        with pytest.raises(ws.SongUnavailable):
            ws.build_timeline(song, "Nope", None, 0, 0)
        with pytest.raises(ws.SongUnavailable):
            ws.build_timeline(song, "Section A", (9, 12), 0, 0)

    def test_three_four_charts_are_refused_for_now(self):
        song = lib_song("Blue Bossa")
        song["meter"] = "3/4"
        with pytest.raises(ws.SongUnavailable):
            ws.build_timeline(song, "Section A", None, 0, 0)


# ================================================================ 4. difficulty changes the music, and the voice-leading is sensible


class TestDifficulty:
    def lines(self, who="alto", title="Blue Bossa", section="Section A"):
        out = {}
        for level in we.LEVELS:
            tones, first, style = ws.VARIANTS[level][0]
            pl, built, abc, _c, song = build_tune(who, title, section, level, tones=tones, first=first, style=style)
            out[level] = (built, abc, oracle.read_tune(abc))
        return out

    def test_tempo_note_count_and_rhythm_all_grow_with_the_level(self):
        L = self.lines()
        bpm = [L[x][0].bpm for x in we.LEVELS]
        count = [sum(1 for t in L[x][2] if t[2] is not None) for x in we.LEVELS]
        values = [{t[1] for t in L[x][2]} for x in we.LEVELS]
        assert bpm == sorted(bpm) and len(set(bpm)) == 3
        assert count[0] < count[1] < count[2]
        assert Fraction(1, 2) not in values[0] and Fraction(1, 2) in values[2]
        assert max(values[0]) >= 2 and Fraction(1, 2) in values[2] and Fraction(1, 2) not in values[1]

    def test_the_music_differs_beyond_the_tempo(self):
        L = self.lines()
        strip = lambda abc: re.sub(r"Q:.*\n|T:.*\n", "", abc)
        assert len({strip(L[x][1]) for x in we.LEVELS}) == 3

    def test_beginner_starts_with_thirds_only_intermediate_and_advanced_use_both(self):
        L = self.lines()
        roles = {x: {n["role"] for p in L[x][0].meta["segments"] if p["supported"] for n in p["notes"]} for x in we.LEVELS}
        assert roles["Beginner"] == {"3"}
        assert roles["Intermediate"] >= {"3", "7"} and roles["Advanced"] >= {"3", "7"}

    def test_a_beginner_gets_a_separate_sevenths_exercise_and_the_both_exercise_after(self):
        kinds = [(t, f) for t, f, _s in ws.VARIANTS["Beginner"]]
        assert kinds[:2] == [("thirds", ""), ("sevenths", "")] and ("both", "third") in kinds

    def test_advanced_accents_each_chord_arrival_and_uses_continuous_eighths_in_the_second_variant(self):
        pl, built, abc, _c, song = build_tune("alto", "Blue Bossa", "Section A", "Advanced", tones="both", first="auto", style="eighths")
        tune = oracle.read_tune(abc)
        assert {t[1] for t in tune if t[2] is not None} == {Fraction(1, 2)}
        assert abc.count("!>!") >= 6

    def test_the_second_and_later_variants_are_different_music(self):
        for level in we.LEVELS:
            tunes = set()
            for tones, first, style in ws.VARIANTS[level]:
                _pl, _b, abc, _c, _s = build_tune("tenor", "Blue Bossa", "Section A", level, tones=tones, first=first, style=style)
                tunes.add(re.sub(r"T:.*\n", "", abc))
            assert len(tunes) == len(ws.VARIANTS[level]), level


class TestVoiceLeading:
    def test_the_seventh_of_a_ii_falls_a_half_step_onto_the_third_of_the_v(self):
        pl, built, abc, _c, song = build_tune("alto", "Blue Bossa", "Section A", "Intermediate")
        res = built.meta["resolutions"]
        assert any(r["step"] == "half step" and r["from_chord"].startswith("Bm7b5") and r["to_chord"].startswith("E7") for r in res), res

    def test_the_dominant_seventh_falls_to_the_minor_third_of_the_tonic_by_a_whole_step(self):
        pl, built, abc, _c, song = build_tune("alto", "Blue Bossa", "Section A", "Intermediate")
        assert any(r["from_chord"].startswith("E7") and r["to_chord"].startswith("Am") and r["step"] == "whole step" for r in built.meta["resolutions"])

    def test_resolutions_are_real_intervals_between_the_notes_written(self):
        pl, built, abc, _c, song = build_tune("flute", "Autumn Leaves", "A Section", "Intermediate")
        midis = [m for _o, _b, m, _c2 in oracle.read_tune(abc) if m is not None]
        for r in built.meta["resolutions"]:
            f = next(s for s in built.meta["segments"] if s["bar"] == r["from_bar"])["notes"][-1]
            t = next(s for s in built.meta["segments"] if s["bar"] == r["to_bar"])["notes"][0]
            assert f["midi"] - t["midi"] == (1 if r["step"] == "half step" else 2) and f["midi"] in midis and t["midi"] in midis

    @pytest.mark.parametrize("who", ["flute", "alto", "tenor"])
    def test_leaps_stay_small_and_smoother_never_makes_them_bigger(self, who):
        for level in we.LEVELS:
            tones, first, style = ws.VARIANTS[level][0]
            _p, normal, _a, _c, _s = build_tune(who, "Autumn Leaves", "A Section", level, tones=tones, first=first, style=style)
            _p, smooth, _a2, _c2, _s2 = build_tune(who, "Autumn Leaves", "A Section", level, tones=tones, first=first, style=style, smooth=True)
            assert normal.meta["largest_leap"] <= 12
            assert smooth.meta["mean_leap"] <= normal.meta["mean_leap"] + 1e-9 and smooth.meta["largest_leap"] <= normal.meta["largest_leap"]

    def test_register_stays_inside_the_instruments_window(self):
        for who in INSTRUMENTS:
            pl, built, abc, _c, song = build_tune(who, "Blue Bossa", "Section A", "Advanced", style="cells")
            lo, hi = pl.window("Advanced")
            assert all(lo <= m <= hi for _o, _b, m, _c2 in oracle.read_tune(abc) if m is not None)


# ================================================================ 5. the conversation: create, revise, undo/redo, ownership


def families(plan):
    return [r["family"] for r in plan["items"]]


def slots_of(plan):
    sel = plan["spec"]["song_sel"]
    slots = plan["spec"]["song"]["sections"][sel["section"]]
    if sel.get("bars"):
        slots = slots[sel["bars"][0] - 1:sel["bars"][1]]
    return slots


def check_plan_notes(plan, who_offset):
    for r in plan["items"]:
        if r["family"] == "guide_tones":
            assert oracle.check_tune(r["abc"], slots_of(plan), who_offset) == [], r["title"]


class TestCreate:
    def test_warm_me_up_for_soloing_over_the_active_song(self):
        s = song_session("Blue Bossa")
        resp = ask(s, "Warm me up for soloing over Blue Bossa.")
        plan = plan_of(s)
        text = resp.composed_markdown()
        assert set(families(plan)) == {"guide_tones"} and len(plan["items"]) >= 3
        assert "Built from “Blue Bossa”" in text and "Section A" in text and plan["spec"]["song"]["hash"] in text and "Practice Key" in text
        check_plan_notes(plan, 9)
        assert resp.diagnostics["warmup_song_aware"] and resp.diagnostics["warmup_song"]["title"] == "Blue Bossa"
        assert abs(plan["total_seconds"] - 600) <= 48

    def test_the_stored_chart_is_the_apps_chart_and_the_thirds_and_sevenths_match_the_catalog(self):
        s = song_session("Blue Bossa")
        ask(s, "Give me a guide-tone exercise over the chorus.")
        plan = plan_of(s)
        stored = plan["spec"]["song"]["sections"]["Section A"]
        catalog = lib_song("Blue Bossa")["sections"]["Section A"]
        assert len(stored) == len(catalog)
        for a, b in zip(stored, catalog):
            ta, tb = oracle.chord_tones(a), oracle.chord_tones(b)
            assert ta[:2] == tb[:2], (a, b)               # the app's richer chart (Cm9) still has the catalog chord's third and seventh

    @pytest.mark.parametrize("q", ["Give me a guide-tone exercise over the chorus.", "Practice the thirds and sevenths of these chords.",
                                   "Give me an advanced jazz guide-tone warmup.", "Warm me up for soloing over Blue Bossa."])
    def test_the_requests_in_the_brief_build_a_guide_tone_warmup(self, q):
        s = song_session("Blue Bossa")
        ask(s, q)
        plan = plan_of(s)
        assert set(families(plan)) == {"guide_tones"}
        check_plan_notes(plan, 9)

    def test_advanced_in_the_request_sets_the_level(self):
        s = song_session("Blue Bossa", level="Beginner")
        ask(s, "Give me an advanced jazz guide-tone warmup.")
        assert plan_of(s)["level"] == "Advanced"

    @pytest.mark.parametrize("who,sax,inst,offset", [("flute", None, "Flute", 0), ("alto", ALTO, "Saxophone", 9), ("tenor", TENOR, "Saxophone", 14)])
    @pytest.mark.parametrize("level", list(we.LEVELS))
    def test_flute_alto_and_tenor_at_every_level(self, who, sax, inst, offset, level):
        s = song_session("Autumn Leaves", instrument=inst, sax=sax, level=level)
        ask(s, "Give me a guide-tone exercise over the chorus.", instrument=inst, level=level, key="Bm")
        plan = plan_of(s)
        assert plan["level"] == level and plan["player"]["offset"] == offset and plan["spec"]["song"]["practice_key"] == "Bm"
        check_plan_notes(plan, offset)
        for r in plan["items"]:
            assert all(c["ok"] for c in r["checks"])
            lo, hi = we.make_player(who, "Bm").window(level)
            assert all(lo <= m <= hi for m in r["written_midi"]) and [m - offset for m in r["written_midi"]] == r["sounding_midi"]

    def test_the_chorus_word_uses_the_open_form_section_and_says_so_when_there_is_no_section_called_chorus(self):
        s = song_session("Blue Bossa")
        resp = ask(s, "Give me a guide-tone exercise over the chorus.")
        assert plan_of(s)["spec"]["song_sel"]["section"] in ("Section A", "Head") and "chorus" in resp.composed_markdown().lower()

    def test_an_explicit_section_name_is_honoured_including_names_like_a3_and_the_bridge(self):
        for q, want in (("Give me a guide-tone warmup over the B Section.", "B Section"), ("Give me a guide-tone warmup over the A2.", "A2")):
            s = song_session("Autumn Leaves", instrument="Flute", sax=None)
            ask(s, q, instrument="Flute", key="Bm")
            assert plan_of(s)["spec"]["song_sel"]["section"] == want, q
        s = song_session("All the Things You Are", sax=TENOR)
        ask(s, "Give me a guide-tone warmup over the A3 section.", key="Ab")
        assert plan_of(s)["spec"]["song_sel"]["section"] == "A3"
        s = song_session("Satin Doll")
        ask(s, "Give me a guide-tone warmup over the bridge.", key="C")
        assert plan_of(s)["spec"]["song_sel"]["section"] == "B (Bridge)"

    def test_a_section_the_song_does_not_have_is_said_not_silently_replaced(self):
        s2 = song_session("Autumn Leaves", instrument="Flute", sax=None)
        resp2 = ask(s2, "Give me a guide-tone warmup over the Pre-Chorus.", instrument="Flute", key="Bm")
        text = resp2.composed_markdown()
        assert "couldn't find a section called" in text and "A Section" in text

    def test_a_first_four_bars_request_is_built_at_exactly_four_bars(self):
        s = song_session("Blue Bossa")
        ask(s, "Give me a guide-tone warmup over the first four bars.")
        plan = plan_of(s)
        assert all(r["bars"] == 4 for r in plan["items"]) and plan["spec"]["song_sel"]["bars"] == [1, 4]

    def test_the_practice_key_of_the_chart_decides_the_chords(self):
        s = song_session("Blue Bossa", practice_key="Dm")
        ask(s, "Give me a guide-tone exercise over the chorus.", key="Dm")
        plan = plan_of(s)
        assert plan["spec"]["song"]["practice_key"] == "Dm" and plan["player"]["concert_key"] == "Dm"
        assert plan["spec"]["song"]["sections"]["Section A"][0].startswith("Dm")
        check_plan_notes(plan, 9)

    def test_long_tones_and_guide_tones_can_be_asked_for_together(self):
        s = song_session("Blue Bossa")
        ask(s, "Give me a warmup with long tones and guide tones over Blue Bossa.")
        assert {"long_tones", "guide_tones"} <= set(families(plan_of(s)))
        check_plan_notes(plan_of(s), 9)

    def test_nothing_in_the_app_changes(self):
        s = song_session("Blue Bossa")
        keys = ["instrument", "display_key", "concert_key", "backing_track_bpm", "song", "level", "active_catalog_pick_key"]
        before = {k: copy.deepcopy(s[k]) for k in keys}
        for q in ("Warm me up for soloing over Blue Bossa.", "Just the first four bars.", "Only the bridge.", "Use thirds only.", "Make it more advanced.",
                  "Make the guide-tone movement smoother.", "Change it to tenor sax.", "Explain why those notes work.", "Undo that.", "Redo"):
            ask(s, q)
        assert {k: s[k] for k in keys} == before


class TestChartIdentityAndOwnership:
    def test_a_named_song_that_is_not_active_is_not_silently_substituted(self):
        s = song_session("Blue Bossa")
        resp = ask(s, "Warm me up for soloing over Autumn Leaves.")
        assert wp.current(s) is None
        text = resp.direct_answer
        assert "Autumn Leaves" in text and "Blue Bossa" in text and "select or activate" in text and "won't substitute" in text

    def test_a_named_song_does_not_disturb_a_warmup_already_open(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        before = copy.deepcopy(plan_of(s))
        ask(s, "Warm me up for soloing over Autumn Leaves.")
        assert plan_of(s) == before

    def test_no_active_song_asks_for_one_and_a_general_request_still_gets_an_ordinary_warmup(self):
        s = {"instrument": "Flute", "level": "Intermediate", "_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel"}
        resp = ask(s, "Give me a guide-tone exercise over the chorus.", instrument="Flute")
        assert wp.current(s) is None and "Select the song" in resp.direct_answer
        resp = ask(s, "Warm me up for soloing.", instrument="Flute")
        assert wp.current(s) is not None and "isn't tailored to a song's chords" in resp.composed_markdown() and "guide_tones" not in families(plan_of(s))

    def test_changing_the_active_song_does_not_rewrite_an_earlier_warmup(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        before = copy.deepcopy(plan_of(s))
        activate_song(s, "Autumn Leaves")
        assert plan_of(s) == before
        resp = ask(s, "Next exercise.")
        assert "Blue Bossa" in resp.composed_markdown() and plan_of(s) == before
        ask(s, "Only the bridge.")
        after = plan_of(s)
        assert after["spec"]["song"]["title"] == "Blue Bossa" and after["spec"]["song"]["hash"] == before["spec"]["song"]["hash"]
        assert after["spec"]["song_sel"]["section"] == "Section B"
        check_plan_notes(after, 9)

    def test_another_account_cannot_see_or_change_the_warmup(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        other = song_session("Blue Bossa", user="someone-else")
        resp = ask(other, "Only the bridge.")
        assert wp.current(other) is None and (resp is None or "Section B" not in resp.composed_markdown())

    def test_a_workspace_switch_hides_the_warmup(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        s["_suite_active_workspace_id"] = "elsewhere"
        assert wp.current(s) is None

    def test_span_requests_stay_with_the_existing_exercise_code(self):
        s = song_session("Blue Bossa")
        for q in ("Give me a guide-tone exercise over Dm7 to G7", "Show me the guide tones", "What are guide tones over the chorus?"):
            assert wp.handle(q, s, ctx()) is None, q


class TestRevisions:
    def fresh(self, **kw):
        s = song_session("Blue Bossa", **kw)
        ask(s, "Warm me up for soloing over Blue Bossa.")
        return s

    def test_just_the_first_four_bars(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Just the first four bars.")
        plan = plan_of(s)
        assert all(r["bars"] == 4 for r in plan["items"]) and plan["spec"]["song_sel"]["bars"] == [1, 4]
        assert "What changed" in resp.composed_markdown() and "bars 1–4" in resp.composed_markdown()
        check_plan_notes(plan, 9)
        assert abs(plan["total_seconds"] - 600) <= 100            # the minutes are kept; plays are re-planned
        ask(s, "Undo that.")
        assert plan_of(s) == before

    def test_the_last_four_and_a_bar_range_and_back_to_all(self):
        s = self.fresh()
        ask(s, "Use the last 4 bars.")
        assert plan_of(s)["spec"]["song_sel"]["bars"] == [5, 8]
        ask(s, "bars 3 to 6")
        assert plan_of(s)["spec"]["song_sel"]["bars"] == [3, 6]
        check_plan_notes(plan_of(s), 9)
        ask(s, "Use the whole section.")
        assert plan_of(s)["spec"]["song_sel"]["bars"] is None

    def test_a_bar_range_that_does_not_exist_is_refused_and_changes_nothing(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "bars 5 to 20")
        assert plan_of(s) == before and "unchanged" in resp.direct_answer

    def test_only_the_bridge(self):
        s = self.fresh()
        resp = ask(s, "Only the bridge.")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["section"] == "Section B" and "Section B" in resp.composed_markdown()
        assert all("Section B" in r["title"] for r in plan["items"])
        check_plan_notes(plan, 9)

    def test_an_unknown_section_is_refused_with_the_real_names(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Only the pre-chorus.")
        assert plan_of(s) == before and "Section A" in resp.direct_answer

    def test_use_thirds_only_then_the_sevenths_then_both(self):
        s = self.fresh()
        ask(s, "Use thirds only.")
        plan = plan_of(s)
        roles = {n["role"] for r in plan["items"] for p in r["meta"]["segments"] if p["supported"] for n in p["notes"]}
        assert roles == {"3"} and plan["spec"]["tones"] == "thirds"
        check_plan_notes(plan, 9)
        ask(s, "Now practice the sevenths.")
        roles = {n["role"] for r in plan_of(s)["items"] for p in r["meta"]["segments"] if p["supported"] for n in p["notes"]}
        assert roles == {"7"}
        check_plan_notes(plan_of(s), 9)
        ask(s, "Practice the thirds and sevenths.")
        roles = {n["role"] for r in plan_of(s)["items"] for p in r["meta"]["segments"] if p["supported"] for n in p["notes"]}
        assert roles == {"3", "7"}

    def test_smoother_reduces_the_leaps_or_says_it_cannot(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Make the guide-tone movement smoother.")
        after = plan_of(s)
        if after != before:
            assert after["spec"]["smooth"] and "smoother" in resp.composed_markdown()
            check_plan_notes(after, 9)
            for a, b in zip([r for r in after["items"] if r["family"] == "guide_tones"], [r for r in before["items"] if r["family"] == "guide_tones"]):
                assert a["meta"]["mean_leap"] <= b["meta"]["mean_leap"] + 1e-9
        else:
            assert "already" in resp.direct_answer and "smooth" in resp.direct_answer
        again = copy.deepcopy(plan_of(s))
        resp = ask(s, "Make the guide-tone movement smoother.")
        assert plan_of(s) == again and "unchanged" in resp.direct_answer

    def test_more_advanced_changes_the_music_not_just_the_label(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        ask(s, "Make it more advanced.")
        after = plan_of(s)
        assert after["level"] == "Advanced" and after["items"][0]["bpm"] > before["items"][0]["bpm"]
        assert {r["abc"] for r in after["items"]}.isdisjoint({r["abc"] for r in before["items"]})
        check_plan_notes(after, 9)

    def test_make_the_second_exercise_slower_changes_only_that_exercise(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        ask(s, "Make the second exercise slower.")
        after = plan_of(s)
        assert after["items"][1]["bpm"] < before["items"][1]["bpm"]
        for i, (a, b) in enumerate(zip(after["items"], before["items"])):
            if i != 1:
                assert a["abc"] == b["abc"] and a["bpm"] == b["bpm"]
        assert after["items"][1]["abc"].split("K:")[1] == before["items"][1]["abc"].split("K:")[1]

    def test_change_it_to_tenor_sax_rewrites_every_exercise_in_the_same_concert_key(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Change it to tenor sax.")
        after = plan_of(s)
        assert after["player"]["key"] == "tenor" and after["player"]["offset"] == 14 and after["spec"]["song"]["hash"] == before["spec"]["song"]["hash"]
        assert after["player"]["concert_key"] == before["player"]["concert_key"] and "instrument" in resp.composed_markdown()
        check_plan_notes(after, 14)
        assert after["items"][0]["abc"] != before["items"][0]["abc"]
        ask(s, "Undo that.")
        assert plan_of(s) == before
        ask(s, "Redo")
        assert plan_of(s) == after

    def test_change_to_flute_and_a_piano_without_long_tones(self):
        s = self.fresh()
        ask(s, "Change it to flute.")
        assert plan_of(s)["player"]["key"] == "flute"
        check_plan_notes(plan_of(s), 0)

    def test_explain_why_those_notes_work_uses_the_stored_chords_and_creates_no_version(self):
        s = self.fresh()
        versions = wp.history(s)["versions"]
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Explain why those notes work.")
        text = resp.composed_markdown()
        assert "Why these notes work" in text and "Bm7b5" in text and "half step" in text and "third" in text
        assert plan_of(s) == before and wp.history(s)["versions"] == versions

    def test_undo_and_redo_restore_each_exact_stored_version_through_a_whole_conversation(self):
        s = self.fresh()
        versions = [copy.deepcopy(plan_of(s))]
        for q in ("Just the first four bars.", "Only the bridge.", "Use thirds only.", "Make it more advanced.", "Change it to tenor sax.", "Make the second exercise slower."):
            ask(s, q)
            if plan_of(s) != versions[-1]:
                versions.append(copy.deepcopy(plan_of(s)))
        assert len(versions) >= 6
        for expect in reversed(versions[:-1]):
            ask(s, "Undo that.")
            assert plan_of(s) == expect
        for expect in versions[1:]:
            ask(s, "Redo")
            assert plan_of(s) == expect

    def test_unrelated_exercises_survive_every_song_revision_byte_for_byte(self):
        s = song_session("Blue Bossa")
        ask(s, "Give me a warmup with long tones and guide tones over Blue Bossa.")
        long_before = [copy.deepcopy(r) for r in plan_of(s)["items"] if r["family"] == "long_tones"]
        assert long_before
        for q in ("Just the first four bars.", "Only the bridge.", "Use thirds only.", "Make the guide-tone movement smoother."):
            ask(s, q)
            now = [r for r in plan_of(s)["items"] if r["family"] == "long_tones"]
            assert [r["abc"] for r in now] == [r["abc"] for r in long_before] and [r["bpm"] for r in now] == [r["bpm"] for r in long_before], q

    def test_song_operations_on_an_ordinary_warmup_are_refused_in_words(self):
        s = {"instrument": "Flute", "level": "Intermediate", "_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel"}
        ask(s, "Give me a 5-minute warmup", instrument="Flute")
        before = copy.deepcopy(plan_of(s))
        for q in ("Just the first four bars.", "Only the bridge.", "Use thirds only.", "Make the guide-tone movement smoother."):
            resp = ask(s, q, instrument="Flute")
            assert plan_of(s) == before and "isn't built from a song" in resp.direct_answer, q

    def test_unsupported_operations_on_a_guide_tone_item_are_refused_not_guessed(self):
        s = self.fresh()
        before = copy.deepcopy(plan_of(s))
        versions = wp.history(s)["versions"]
        for q in ("Change the interval exercise to fourths", "Make it swing", "Add accents to the guide tones"):
            ask(s, q)
            assert plan_of(s) == before and wp.history(s)["versions"] == versions, q

    def test_a_chart_with_a_dim_chord_keeps_working_through_revisions(self):
        s = song_session("All the Things You Are", sax=TENOR)
        ask(s, "Give me a guide-tone exercise over the chorus.", key="Ab")
        ask(s, "Only A3.", key="Ab")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["section"] == "A3"
        meta = plan["items"][0]["meta"]
        assert [(u["bar"], u["concert"]) for u in meta["unsupported"]] == [(8, "Bdim7")]
        assert resp_has_rests(plan)


def resp_has_rests(plan):
    return all("Rests mark chords" in " ".join(r["listen"]) for r in plan["items"] if r["family"] == "guide_tones")


class TestDurationAndDefaults:
    def test_ten_minutes_by_default_and_a_stated_length_is_honoured(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        assert plan_of(s)["minutes"] == 10
        s2 = song_session("Blue Bossa")
        ask(s2, "Give me a 6-minute guide-tone warmup over the chorus.")
        p = plan_of(s2)
        assert p["minutes"] == 6 and abs(p["total_seconds"] - 360) <= 40

    def test_one_play_is_one_pass_through_the_section_and_the_seconds_add_up(self):
        s = song_session("Blue Bossa")
        ask(s, "Warm me up for soloing over Blue Bossa.")
        p = plan_of(s)
        for r in p["items"]:
            assert abs(r["pass_seconds"] - r["bars"] * 4 * 60 / r["bpm"]) < 0.02
            assert abs(r["seconds"] - (r["reps"] * r["pass_seconds"] + (r["reps"] - 1) * p["gap_seconds"])) < 0.1
        assert abs(p["total_seconds"] - (sum(r["seconds"] for r in p["items"]) + (len(p["items"]) - 1) * p["transition_seconds"])) < 0.2

    def test_a_short_section_that_cannot_fill_the_time_says_so(self):
        s = song_session("Blue Bossa")
        ask(s, "Give me a guide-tone warmup over the first two bars.")
        p = plan_of(s)
        assert p["total_seconds"] < p["target_seconds"] and "Planned playing time" in ask(s, "Show the whole warmup.").composed_markdown()


class TestDefaultSection:
    def synthetic(self, **sections):
        song = lib_song("Blue Bossa")
        song["sections"] = sections
        song["order"] = list(sections)
        song["active_section"] = next(iter(sections))
        return song

    def test_an_intro_is_not_the_default_when_the_form_itself_is_available(self):
        song = self.synthetic(Intro=["Cm7"] * 2, Chorus=["Cm7"] * 8, Outro=["Cm7"] * 3)
        assert ws.pick_section(song, "") == ("Chorus", "not_an_intro")

    def test_with_no_chorus_the_longest_non_intro_section_is_used(self):
        song = self.synthetic(Outro=["Cm7"] * 3, Tune=["Cm7"] * 6, B=["Fm7"] * 4)
        assert ws.pick_section(song, "") == ("Tune", "not_an_intro")

    def test_the_open_section_is_kept_when_it_is_part_of_the_form(self):
        song = lib_song("Blue Bossa")
        assert ws.pick_section(song, "") == ("Section A", "active_section")

    def test_a_named_section_always_wins(self):
        song = self.synthetic(Intro=["Cm7"] * 2, **{"Verse 1": ["Cm7"] * 8}, Chorus=["Cm7"] * 8)
        assert ws.pick_section(song, "verse") == ("Verse 1", "named")


class TestFindingASectionByTheSongsOwnNames:
    def test_names_aliases_and_lone_letters(self):
        order = lib_song("Satin Doll")["order"]
        assert ws.find_section(order, "only the bridge") == "B (Bridge)" and ws.find_section(order, "Use A2.") == "A2" and ws.find_section(order, "the turnaround") == "Turnaround"
        assert ws.find_section(["A", "B"], "give me a warmup") == "" and ws.find_section(["A", "B"], "over section b") == "B" and ws.find_section(["A", "B"], "the A section") == "A"

    def test_a_song_title_never_matches_a_section(self):
        order = lib_song("Take the A Train")["order"]
        assert ws.find_section(order, "Warm me up for soloing over Take the A Train") == ""

    def test_a_revision_names_a_section_only_as_an_instruction(self):
        order = lib_song("All the Things You Are")["order"]
        assert wp.parse_revision("Only A3.", order) == {"op": "section", "section": "A3"}
        assert wp.parse_revision("Use the bridge", order) == {"op": "section", "section": "Bridge"}
        assert (wp.parse_revision("Make the second exercise slower", order) or {}).get("op") == "item_slower"


class TestAutumnLeavesAsTheAppCharts:
    """The app charts Autumn Leaves with richer chords than the bare catalog record (Bm9, Em9, A13); the notes follow the chart the app shows."""

    def test_soloing_over_it_follows_the_apps_chords_not_the_bare_catalog_triads(self):
        s = song_session("Autumn Leaves", instrument="Flute", sax=None)
        ask(s, "Warm me up for soloing over Autumn Leaves.", instrument="Flute", key="Bm")
        plan = plan_of(s)
        section = plan["spec"]["song_sel"]["section"]
        chart = plan["spec"]["song"]["sections"][section]
        assert section == "A Section" and "Bm9" in chart and "A13" in chart
        check_plan_notes(plan, 0)
        sevenths = {n["name"] for r in plan["items"] for p in r["meta"]["segments"] if p["supported"] and p["concert"] == "Bm9" for n in p["notes"] if n["role"] == "7"}
        assert sevenths <= {"A"}                       # the seventh of Bm9, which the bare catalog triad does not have

    def test_the_catalog_triad_alone_still_gets_only_its_third(self):
        pl, built, abc, _c, song = build_tune("flute", "Autumn Leaves", "A Section", "Intermediate", tones="sevenths", first="", style="pulse")
        bm = [p for p in built.meta["segments"] if p["concert"] == "Bm"]
        assert bm and all({n["role"] for n in p["notes"]} == {"3"} for p in bm)

    def test_split_bars_in_the_c_section_are_timed_by_halves(self):
        pl, built, abc, _c, song = build_tune("alto", "Autumn Leaves", "C Section", "Intermediate")
        assert oracle.check_tune(abc, song["sections"]["C Section"], pl.offset) == []
        assert any(p["beats"] == 2.0 and p["concert"] == "Bm7" for p in built.meta["segments"])
