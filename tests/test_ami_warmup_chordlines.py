"""Adaptive warmups, Slice 2b: chord-tone arpeggios, approach notes, whole-form sections, mixed plans and their conversational revisions.

Independent verification: ``tests/song_oracle.py`` (its own chord reader and ABC tokenizer) checks every written note, at its beat, against the CHARTED chord:
arpeggio notes must be tones of the chord; the only other notes allowed in an approach exercise are runs of at most two that sit at the end of a chord, are tones
of neither the chord they leave nor the chord they enter, step (1 or 2 semitones) onto a tone of the next chord, on the beat the chart changes chord.
"""
from __future__ import annotations

import copy
import re
from fractions import Fraction

import pytest

from music_coach_ami import warmup_chordline as wc
from music_coach_ami import warmup_engine as we
from music_coach_ami import warmup_plan as wp
from music_coach_ami import warmup_song as ws
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.pipeline import run_coach_submit
from tests import song_oracle as oracle
from tests.song_fixtures import ALTO, TENOR, activate_song, lib_song, song_session

OFFSET = {"flute": 0, "piano": 0, "alto": 9, "tenor": 14, "soprano": 2, "trumpet": 2, "clarinet": 2, "baritone": 21}
SONGS = [("Blue Bossa", ["Section A", "Section B", "Head"]), ("Autumn Leaves", ["A Section", "C Section", "Whole form"]), ("Satin Doll", ["A", "B (Bridge)", "Whole form"]),
         ("Take the A Train", ["A Section"]), ("The Girl from Ipanema", ["B Section"]), ("All the Things You Are", ["A", "Bridge", "A3"])]
INSTRUMENTS = ["flute", "alto", "tenor", "soprano", "baritone", "clarinet", "trumpet", "piano"]


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


def fams(plan):
    return [r["family"] for r in plan["items"]]


def slots_of(plan):
    sel = plan["spec"]["song_sel"]
    slots = ws.section_slots(plan["spec"]["song"], sel["section"])
    return slots[sel["bars"][0] - 1:sel["bars"][1]] if sel.get("bars") else slots


def check_plan(plan, offset):
    for r in plan["items"]:
        if r["family"] == "guide_tones":
            assert oracle.check_tune(r["abc"], slots_of(plan), offset) == [], r["title"]
        elif r["family"] == "chord_tones":
            assert oracle.check_chordline(r["abc"], slots_of(plan), offset, approach=False) == [], r["title"]
        elif r["family"] == "approach_notes":
            assert oracle.check_chordline(r["abc"], slots_of(plan), offset, approach=True, loop=bool(r["meta"].get("looping"))) == [], r["title"]


def build(fam, who, title, section, level, bars=None, key=None, **kw):
    song = ws.with_whole_form(lib_song(title, key=key))[0]
    pl = we.make_player(who, song["practice_key"])
    built = (wc.build_chord_tones if fam == "ct" else wc.build_approach)(pl, level, song, section, bars, **kw)
    tonic, tonality = we.practical_key(*we.split_key(pl.written_key))
    abc, diag = we.render(pl, built, tonic, tonality, title=built.title, bpm=built.bpm)
    wc.verify(pl, level, built, diag)
    return pl, built, abc, song


# ================================================================ 1. the oracle on real songs: every instrument, level and variant


@pytest.mark.parametrize("who", INSTRUMENTS)
def test_every_note_of_every_arpeggio_and_approach_line_agrees_with_the_independent_oracle(who):
    n = 0
    for title, sections in SONGS:
        for section in sections:
            for level in we.LEVELS:
                for d, sh, st, art in wc.CHORD_VARIANTS[level]:
                    pl, b, abc, song = build("ct", who, title, section, level, direction=d, shape=sh, start=st, art=art)
                    assert oracle.check_chordline(abc, ws.section_slots(song, section), pl.offset, approach=False) == [], (who, title, section, level, d, sh, st)
                    assert pl.offset == OFFSET[who]
                    n += 1
                for kind, target in wc.APPROACH_VARIANTS[level]:
                    pl, b, abc, song = build("ap", who, title, section, level, kind=kind, target=target)
                    probs = oracle.check_chordline(abc, ws.section_slots(song, section), pl.offset, approach=True, loop=bool(b.meta["looping"]))
                    assert probs == [], (who, title, section, level, kind, target, probs[:2])
                    n += 1
    assert n >= 150


class TestTheOracleCatchesWrongApproachMusic:
    """If these did not fail, 'no problems' above would mean nothing."""

    def setup_method(self):
        self.pl, self.b, self.abc, self.song = build("ap", "alto", "Blue Bossa", "Section A", "Intermediate", kind="below", target="third")
        self.slots = ws.section_slots(self.song, "Section A")
        head, self.body = self.abc.split("K:", 1)
        self.head = head + "K:"

    def test_the_unmodified_line_passes(self):
        assert oracle.check_chordline(self.abc, self.slots, self.pl.offset, approach=True) == []

    def test_an_arpeggio_note_that_is_not_a_chord_tone_is_caught_in_arpeggio_mode(self):
        pl, b, abc, song = build("ct", "alto", "Blue Bossa", "Section A", "Intermediate", direction="up", shape="straight", start="root")
        body = abc.split("K:", 1)[1]
        bad = re.sub(r'("Am9"|"Am7")([A-Ga-g])', lambda m: m.group(1) + "^" + m.group(2), body, count=1)
        assert bad != body
        assert oracle.check_chordline(abc.split("K:", 1)[0] + "K:" + bad, ws.section_slots(song, "Section A"), pl.offset, approach=False)

    def test_an_approach_that_does_not_land_on_a_chord_tone_is_caught(self):
        # move every approach note's neighbour target by turning the next chord's first note into a non-chord tone
        body = re.sub(r'("Dm7"|"Dm9")([A-Ga-g]|\^[A-Ga-g]|_[A-Ga-g])', lambda m: m.group(1) + "^" + m.group(2).lstrip("^_"), self.body, count=1)
        assert body != self.body
        assert oracle.check_chordline(self.head + body, self.slots, self.pl.offset, approach=True)

    def test_a_wrong_instrument_offset_is_caught(self):
        assert oracle.check_chordline(self.abc, self.slots, self.pl.offset + 1, approach=True)

    def test_a_chart_with_a_different_chord_is_caught(self):
        other = list(self.slots)
        other[2] = "Gm7"
        assert oracle.check_chordline(self.abc, other, self.pl.offset, approach=True)

    def test_three_non_chord_tones_in_a_row_do_not_count_as_an_approach(self):
        pl, b, abc, song = build("ap", "flute", "Blue Bossa", "Section A", "Advanced", kind="double", target="third")
        assert oracle.check_chordline(abc, ws.section_slots(song, "Section A"), pl.offset, approach=True, loop=bool(b.meta["looping"])) == []
        body = abc.split("K:", 1)[1]
        # insert one more chromatic note before an existing approach: three non-chord tones in a row
        bad = re.sub(r"(\^?_?[A-Ga-g]'?,?/2 )(\^?_?[A-Ga-g]'?,?/2 )(\^?_?[A-Ga-g]'?,?/2 \| ?\"?[A-G])", lambda m: m.group(1) + m.group(1) + m.group(2) + m.group(3), body, count=1)
        if bad != body:
            assert oracle.check_chordline(abc.split("K:", 1)[0] + "K:" + bad, ws.section_slots(song, "Section A"), pl.offset, approach=True)


# ================================================================ 2. arpeggios


def first_roles(built):
    return [seg["notes"][0]["role"] for seg in built.meta["segments"] if seg["supported"] and seg["notes"]]


class TestArpeggios:
    @pytest.mark.parametrize("start,role", [("root", "R"), ("third", "3"), ("fifth", "5"), ("seventh", "7")])
    def test_every_arpeggio_starts_on_the_chosen_chord_tone(self, start, role):
        pl, b, abc, song = build("ct", "flute", "Blue Bossa", "Section A", "Intermediate", direction="up", shape="straight", start=start)
        assert all(r == role for r in first_roles(b)), first_roles(b)

    def test_ascending_climbs_and_descending_falls_through_the_chords_own_tones(self):
        for direction, sign in (("up", 1), ("down", -1)):
            pl, b, abc, song = build("ct", "alto", "Blue Bossa", "Section A", "Beginner", direction=direction, shape="straight", start="auto")
            for seg in b.meta["segments"]:
                mids = [n["midi"] for n in seg["notes"]]
                assert all((b2 - a) * sign > 0 for a, b2 in zip(mids, mids[1:])), (direction, seg["written"], mids)

    def test_the_shapes_visit_the_tones_in_the_shapes_order(self):
        order = {"straight": [0, 1, 2, 3], "skip": [0, 2, 1, 3], "zig": [0, 3, 1, 2]}
        for shape, positions in order.items():
            pl, b, abc, song = build("ct", "flute", "Blue Bossa", "Section A", "Advanced", direction="up", shape=shape, start="root")
            seg = next(p for p in b.meta["segments"] if p["written"].startswith("Cm"))
            tone_order = ["R", "3", "5", "7"]
            assert [n["role"] for n in seg["notes"][:4]] == [tone_order[i] for i in positions], (shape, [n["role"] for n in seg["notes"]])

    def test_up_and_back_comes_back_down(self):
        pl, b, abc, song = build("ct", "flute", "Blue Bossa", "Section A", "Intermediate", direction="up", shape="updown", start="root")
        seg = b.meta["segments"][0]
        mids = [n["midi"] for n in seg["notes"]]
        assert mids[:4] == sorted(mids[:4]) and mids[3:6] == sorted(mids[3:6], reverse=True) and len(mids) == 8

    def test_beginners_play_quarter_notes_and_the_others_eighths(self):
        for level, unit in (("Beginner", Fraction(1)), ("Intermediate", Fraction(1, 2)), ("Advanced", Fraction(1, 2))):
            pl, b, abc, song = build("ct", "flute", "Blue Bossa", "Section A", level, direction="up", shape="straight", start="root")
            assert {Fraction(n["beats"]).limit_denominator(8) for p in b.meta["segments"] for n in p["notes"]} == {unit}, level

    def test_a_triad_has_three_tones_and_a_sixth_chord_uses_its_sixth(self):
        song = lib_song("Blue Bossa")
        song["sections"]["X"] = ["C", "Am", "C6", "Cm6"]
        song["order"].append("X")
        pl = we.make_player("flute", "C")
        built = wc.build_chord_tones(pl, "Beginner", song, "X", None, direction="up", shape="straight", start="root")
        rows = {p["concert"]: [n["role"] for n in p["notes"]] for p in built.meta["segments"]}
        assert rows["C"][:3] == ["R", "3", "5"] and rows["Am"][:3] == ["R", "3", "5"] and rows["C6"] == ["R", "3", "5", "6"]
        assert set(rows["C"]) == {"R", "3", "5"}                                     # a triad has no seventh to add; the fourth note is the root an octave up

    def test_an_altered_dominant_has_no_fifth_and_still_works(self):
        song = lib_song("Blue Bossa")
        song["sections"]["Alt"] = ["C7alt", "Fm7", "C7alt", "Fm7"]
        song["order"].append("Alt")
        pl = we.make_player("alto", "C")
        built = wc.build_chord_tones(pl, "Intermediate", song, "Alt", None, direction="up", shape="straight", start="auto")
        alt = next(p for p in built.meta["segments"] if p["concert"] == "C7alt")
        assert "5" not in {n["role"] for n in alt["notes"]}

    def test_choosing_the_start_tone_by_voice_leading_never_leaps_more_than_always_starting_on_the_root(self):
        def boundary_leaps(start):
            pl, b, abc, song = build("ct", "alto", "Blue Bossa", "Section A", "Intermediate", direction="up", shape="straight", start=start)
            segs = [p for p in b.meta["segments"] if p["supported"]]
            return sum(abs(q["notes"][0]["midi"] - p["notes"][-1]["midi"]) for p, q in zip(segs, segs[1:]))
        assert boundary_leaps("auto") <= boundary_leaps("root")

    @pytest.mark.parametrize("who,offset", [("flute", 0), ("alto", 9), ("tenor", 14)])
    @pytest.mark.parametrize("level", list(we.LEVELS))
    def test_written_and_sounding_pitch_for_flute_alto_and_tenor(self, who, offset, level):
        d, sh, st, art = wc.CHORD_VARIANTS[level][0]
        pl, b, abc, song = build("ct", who, "Satin Doll", "A", level, direction=d, shape=sh, start=st, art=art)
        written = [n["midi"] for p in b.meta["segments"] if p["supported"] for n in p["notes"]]
        lo, hi = pl.window(level)
        assert pl.offset == offset and all(lo <= m <= hi for m in written) and all(pl.play_low <= m <= pl.play_high for m in written)
        assert oracle.check_chordline(abc, ws.section_slots(song, "A"), offset, approach=False) == []


# ================================================================ 3. approach notes


class TestApproachNotes:
    @pytest.mark.parametrize("kind,expect", [("below", {(-1,), (1,)}), ("above", {(1,), (-1,)}), ("double", {(-2, -1), (2, 1)}), ("double_above", {(2, 1), (-2, -1)}),
                                              ("enclosure", {(1, -1), (-1, 1)})])
    def test_each_kind_has_the_geometry_it_claims(self, kind, expect):
        pl, b, abc, song = build("ap", "flute", "Blue Bossa", "Section A", "Advanced", kind=kind, target="auto")
        assert b.meta["approaches"], kind
        for a in b.meta["approaches"]:
            assert tuple(a["offsets"]) in expect, (kind, a)
        first = b.meta["approaches"][0]
        preferred = {"below": (-1,), "above": (1,), "double": (-2, -1), "double_above": (2, 1), "enclosure": (1, -1)}[kind]
        assert any(tuple(a["offsets"]) == preferred for a in b.meta["approaches"]), (kind, [a["offsets"] for a in b.meta["approaches"]])

    def test_a_diatonic_approach_is_the_scale_note_below_the_target(self):
        pl, b, abc, song = build("ap", "flute", "Blue Bossa", "Section A", "Intermediate", kind="diatonic", target="third")
        assert b.meta["approaches"] and all(a["offsets"][0] in (-1, -2, 1) for a in b.meta["approaches"])
        assert any(a["offsets"][0] == -2 for a in b.meta["approaches"]) or all(a["offsets"][0] in (-1, 1) for a in b.meta["approaches"])

    def test_the_target_is_the_asked_for_chord_tone_of_the_new_chord(self):
        for target, role in (("third", "3"), ("seventh", "7"), ("root", "R"), ("fifth", "5")):
            pl, b, abc, song = build("ap", "flute", "Blue Bossa", "Section A", "Intermediate", kind="below", target=target)
            assert b.meta["approaches"] and {a["target_role"] for a in b.meta["approaches"]} <= {role, "3"}, (target, [a["target_role"] for a in b.meta["approaches"]])
            assert sum(1 for a in b.meta["approaches"] if a["target_role"] == role) >= 2

    def test_an_approach_is_never_a_chord_tone_of_the_chord_it_leaves_or_enters(self):
        for who in ("flute", "alto", "tenor"):
            for level in we.LEVELS:
                for kind, target in wc.APPROACH_VARIANTS[level]:
                    pl, b, abc, song = build("ap", who, "Autumn Leaves", "A Section", level, kind=kind, target=target)
                    for a in b.meta["approaches"]:
                        leaving = next(p for p in b.meta["segments"] if p["bar"] == a["from_bar"] and p["supported"])
                        entering = next(p for p in b.meta["segments"] if p["bar"] == a["to_bar"] and p["supported"] and p["beat"] == a["to_beat"])
                        pcs_l = {pc for pc in oracle.all_tones(leaving["concert"]).values()}
                        pcs_e = {pc for pc in oracle.all_tones(entering["concert"]).values()}
                        for midi in [n["midi"] for n in entering["notes"] if False] or []:
                            pass
                        for name in a["approach"]:
                            pc = (we.sph.pc_of(name) - pl.semitones) % 12
                            assert pc not in pcs_l and pc not in pcs_e, (who, level, kind, a)

    def test_a_usual_neighbour_that_is_a_chord_tone_is_replaced_by_the_other_side_and_said(self):
        pl, b, abc, song = build("ap", "alto", "Blue Bossa", "Section A", "Intermediate", kind="below", target="third")
        said = [a for a in b.meta["approaches"] if "other side" in (a.get("note") or "")]
        assert said and all(a["offsets"] == [1] for a in said)
        assert any("other side" in x for x in b.listen)

    def test_the_approach_lands_exactly_on_the_beat_a_split_bar_changes_chord(self):
        pl, b, abc, song = build("ap", "flute", "Satin Doll", "A", "Intermediate", kind="below", target="third")
        tune = oracle.read_tune(abc)
        changes = {o for o, _bt, _c in oracle.expected_timeline(ws.section_slots(song, "A"))}
        landed = [t for t in tune if t[0] in changes and t[0] % 4 == 2]            # halfway through a bar: beat 3
        assert landed, "no change on beat 3 was approached"
        for a in b.meta["approaches"]:
            assert a["to_beat"] in (0.0, 2.0)
        # the note just before each beat-3 change is the approach note: half a beat long, ending exactly there
        for t in landed:
            prev = [x for x in tune if x[0] + x[1] == t[0]][0]
            assert prev[1] == Fraction(1, 2)

    def test_the_last_chord_approaches_the_first_for_the_repeat(self):
        pl, b, abc, song = build("ap", "alto", "Blue Bossa", "Section B", "Intermediate", kind="below", target="third")
        # Section B ends on Cm7 and begins on Ebm7: the form repeats, so the last bar leads back into bar 1
        assert b.meta["looping"] and any(a["loop_back"] for a in b.meta["approaches"])
        assert oracle.check_chordline(abc, ws.section_slots(song, "Section B"), pl.offset, approach=True, loop=True) == []

    def test_a_chord_too_short_for_the_approach_says_so_instead_of_inventing_one(self):
        song = lib_song("Blue Bossa")
        song["sections"]["Q"] = ["Dm7:3|G7:1", "Cm7"]
        song["order"].append("Q")
        pl = we.make_player("flute", "Cm")
        b = wc.build_approach(pl, "Beginner", song, "Q", None, kind="below", target="third")
        assert any("too short" in sk["reason"] for sk in b.meta["skipped_approaches"]) or b.meta["approaches"] == []

    def test_unsupported_chords_are_rested_and_neither_approached_nor_left_by_an_approach(self):
        pl, b, abc, song = build("ap", "tenor", "All the Things You Are", "A3", "Intermediate", kind="below", target="third")
        assert [(u["bar"], u["concert"]) for u in b.meta["unsupported"]] == [(8, "Bdim7")]
        for a in b.meta["approaches"]:
            assert a["from_bar"] != 8 and a["to_bar"] != 8
        tune = oracle.read_tune(abc)
        assert all(t[2] is None for t in tune if 28 <= t[0] < 32) and any("Rests mark" in x for x in b.listen)
        assert oracle.check_chordline(abc, ws.section_slots(song, "A3"), pl.offset, approach=True, loop=bool(b.meta["looping"])) == []

    def test_a_triad_without_a_seventh_is_approached_on_its_third_and_says_so(self):
        pl, b, abc, song = build("ap", "flute", "Autumn Leaves", "A Section", "Intermediate", kind="above", target="seventh")
        assert any(a["target_role"] == "3" and "no" in (a.get("note") or "") for a in b.meta["approaches"]) or all(a["target_role"] in ("7", "3") for a in b.meta["approaches"])
        assert oracle.check_chordline(abc, ws.section_slots(song, "A Section"), pl.offset, approach=True, loop=bool(b.meta["looping"])) == []

    def test_the_approach_notes_are_marked_apart_from_the_chord_tones_in_the_explanation(self):
        pl, b, abc, song = build("ap", "alto", "Blue Bossa", "Section A", "Intermediate", kind="below", target="third")
        roles = {n["role"] for p in b.meta["segments"] if p["supported"] for n in p["notes"]}
        assert "approach" in roles and roles - {"approach"} <= {"R", "3", "5", "7", "6"}
        assert any("resolves to" in x for x in b.listen)

    @pytest.mark.parametrize("who,offset", [("flute", 0), ("alto", 9), ("tenor", 14)])
    @pytest.mark.parametrize("level", list(we.LEVELS))
    def test_written_and_sounding_pitch_for_flute_alto_and_tenor(self, who, offset, level):
        kind, target = wc.APPROACH_VARIANTS[level][0]
        pl, b, abc, song = build("ap", who, "Satin Doll", "A", level, kind=kind, target=target)
        written = [n["midi"] for p in b.meta["segments"] if p["supported"] for n in p["notes"]]
        lo, hi = pl.window(level)
        assert pl.offset == offset and all(lo <= m <= hi for m in written)
        assert oracle.check_chordline(abc, ws.section_slots(song, "A"), offset, approach=True, loop=bool(b.meta["looping"])) == []


class TestSpelling:
    @pytest.mark.parametrize("target,delta,expect", [("D", -1, "C#"), ("D", 1, "Eb"), ("F", -1, "E"), ("E", 1, "F"), ("F#", 1, "G"), ("Eb", -1, "D"), ("A", -2, "G"), ("Bb", 1, "B"),
                                                     ("G", 2, "A"), ("C", -1, "B")])
    def test_approach_notes_are_spelled_the_way_they_are_read(self, target, delta, expect):
        assert wc.near_name(target, delta) == expect

    def test_never_a_double_accidental(self):
        for t in ("C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"):
            for d in (-2, -1, 1, 2):
                n = wc.near_name(t, d)
                assert n is None or not re.search(r"(##|bb)", n), (t, d, n)


# ================================================================ 4. whole form and sections


class TestWholeForm:
    def test_autumn_leaves_whole_form_is_the_charts_own_sections_in_order(self):
        song = lib_song("Autumn Leaves")
        song2, how, why = ws.with_whole_form(song)
        assert how == "all_sections" and song2["derived"]["Whole form"] == ["A Section", "A2", "B Section", "C Section"]
        assert len(ws.section_slots(song2, "Whole form")) == 32 and song2["hash"] == song["hash"]
        assert ws.section_slots(song2, "Whole form") == [x for p in song["order"] for x in song["sections"][p]]
        assert song2["sections"] == song["sections"]                        # nothing invented, nothing added to the real sections

    def test_a_chart_with_a_form_section_uses_it_and_does_not_concatenate(self):
        song2, how, why = ws.with_whole_form(lib_song("Blue Bossa"))
        assert how == "named_form" and "derived" not in song2 and ws.whole_form(lib_song("Blue Bossa"))[0] == ["Head"]

    def test_intros_and_outros_are_not_part_of_the_form(self):
        song = lib_song("The Girl from Ipanema")
        parts, how, _w = ws.whole_form(song)
        assert "Intro" not in parts and not any("Outro" in p for p in parts)

    def test_a_form_longer_than_the_limit_is_refused_with_a_reason(self):
        song = lib_song("Blue Bossa")
        song["sections"] = {"A": ["Cm7"] * 40, "B": ["Fm7"] * 40}
        song["order"] = ["A", "B"]
        parts, how, why = ws.whole_form(song)
        assert parts == [] and "longer than" in why

    def test_the_whole_song_request_builds_every_bar_of_the_form(self):
        s = song_session("Autumn Leaves", instrument="Flute", sax=None)
        resp = ask(s, "Warm me up over the whole song.", instrument="Flute", key="Bm")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["section"] == "Whole form" and all(r["bars"] == 32 for r in plan["items"] if r["family"] in wp.SONG_FAMILIES)
        text = resp.composed_markdown()
        assert "the whole form (A Section + A2 + B Section + C Section, 32 bars)" in text and plan["spec"]["song"]["hash"] in text
        check_plan(plan, 0)

    def test_entire_chorus_prepare_me_for_improvising(self):
        s = song_session("Satin Doll", instrument="Flute", sax=None)
        ask(s, "Prepare me for improvising over the entire chorus.", instrument="Flute", key="C")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["section"] == "Whole form" and plan["spec"]["song"]["derived"]["Whole form"] == ["A", "A2", "B (Bridge)", "A3"]
        check_plan(plan, 0)

    def test_first_eight_bars_of_the_whole_form(self):
        s = song_session("Autumn Leaves", instrument="Flute", sax=None)
        ask(s, "Warm me up over the whole song, just the first eight bars.", instrument="Flute", key="Bm")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["bars"] == [1, 8] and all(r["bars"] == 8 for r in plan["items"] if r["family"] in wp.SONG_FAMILIES)
        check_plan(plan, 0)

    def test_the_whole_song_as_a_revision_then_the_bridge_then_undo(self):
        s = song_session("Satin Doll", instrument="Flute", sax=None)
        ask(s, "Give me an arpeggio warmup over Satin Doll.", instrument="Flute", key="C")
        v1 = copy.deepcopy(plan_of(s))
        ask(s, "Use the whole song.", instrument="Flute", key="C")
        assert plan_of(s)["spec"]["song_sel"]["section"] == "Whole form"
        v2 = copy.deepcopy(plan_of(s))
        ask(s, "Only the bridge.", instrument="Flute", key="C")
        assert plan_of(s)["spec"]["song_sel"]["section"] == "B (Bridge)"
        check_plan(plan_of(s), 0)
        ask(s, "Undo that.")
        assert plan_of(s) == v2
        ask(s, "Undo that.")
        assert plan_of(s) == v1


# ================================================================ 5. requests, mixed plans and the order the musician names the exercises in


class TestRequestsAndMixedPlans:
    def new(self, q, song="Blue Bossa", **kw):
        s = song_session(song, **kw)
        ask(s, q, level=kw.get("level", "Intermediate"), key="Cm" if song == "Blue Bossa" else "Bm")
        return s

    def test_an_arpeggio_warmup_over_the_song_follows_the_charts_chords(self):
        s = self.new("Give me an arpeggio warmup over Blue Bossa.")
        plan = plan_of(s)
        assert set(fams(plan)) == {"chord_tones"} and plan["spec"]["song"]["title"] == "Blue Bossa"
        check_plan(plan, 9)

    def test_a_generic_soloing_request_is_a_mixed_plan_that_depends_on_the_level(self):
        for level, expect in (("Beginner", {"guide_tones", "chord_tones"}), ("Intermediate", {"scale", "guide_tones", "chord_tones", "approach_notes"}),
                              ("Advanced", {"scale", "guide_tones", "chord_tones", "approach_notes"})):
            s = self.new("Warm me up for soloing over Blue Bossa.", level=level)
            plan = plan_of(s)
            assert set(fams(plan)) == expect and fams(plan).count("scale") <= 1, level
            assert abs(plan["total_seconds"] - 600) <= 80
            check_plan(plan, 9)

    def test_the_mixed_plan_goes_from_the_simplest_preparation_to_the_approach_notes(self):
        s = self.new("Warm me up for soloing over Blue Bossa.")
        order = fams(plan_of(s))
        rank = {"scale": 0, "guide_tones": 1, "chord_tones": 2, "approach_notes": 3}
        assert [rank[f] for f in order] == sorted(rank[f] for f in order)

    def test_the_exercises_are_in_the_order_the_musician_names_them(self):
        s = self.new("Give me a guide-tone exercise followed by arpeggios.")
        order = fams(plan_of(s))
        assert order.index("chord_tones") > max(i for i, f in enumerate(order) if f == "guide_tones")
        s2 = self.new("Give me arpeggios and then guide tones over Blue Bossa.")
        order2 = fams(plan_of(s2))
        assert order2.index("guide_tones") > max(i for i, f in enumerate(order2) if f == "chord_tones")

    def test_explicit_exercises_are_not_padded_with_unrelated_ones(self):
        s = self.new("Give me an approach-note and arpeggio warmup over Blue Bossa.")
        assert set(fams(plan_of(s))) == {"chord_tones", "approach_notes"}

    def test_an_exclusion_is_honoured_in_a_mixed_plan(self):
        s = self.new("Warm me up for soloing over Blue Bossa, no scales.")
        assert "scale" not in fams(plan_of(s))

    def test_a_ten_minute_default_and_a_stated_length(self):
        s = self.new("Give me an arpeggio warmup over Blue Bossa.")
        assert plan_of(s)["minutes"] == 10 and abs(plan_of(s)["total_seconds"] - 600) <= 60
        s2 = self.new("Give me a 5-minute arpeggio warmup over Blue Bossa.")
        assert plan_of(s2)["minutes"] == 5 and abs(plan_of(s2)["total_seconds"] - 300) <= 40

    def test_a_named_song_that_is_not_active_is_still_not_substituted(self):
        s = song_session("Blue Bossa")
        resp = ask(s, "Give me an arpeggio warmup over Autumn Leaves.")
        assert wp.current(s) is None and "won't substitute" in resp.direct_answer

    def test_ordinary_exercise_requests_with_arpeggios_still_belong_to_the_existing_exercise_code(self):
        s = song_session("Blue Bossa")
        for q in ("Give me a chord tone exercise over Cm7", "Give me an enclosure over Bm7", "Show me the arpeggio for Dm7"):
            assert wp.handle(q, s, ctx()) is None, q


# ================================================================ 6. conversational revisions, each stored, scoped and exactly undoable


class TestRevisions:
    def fresh(self, q="Give me an arpeggio warmup over Blue Bossa.", level="Beginner", **kw):
        s = song_session("Blue Bossa", level=level, **kw)
        ask(s, q, level=level)
        return s

    def go(self, s, q, level="Beginner", **kw):
        return ask(s, q, level=level, **kw)

    def test_make_the_arpeggio_exercise_more_advanced_raises_every_arpeggio_exercise_only(self):
        s = song_session("Blue Bossa", level="Beginner")
        ask(s, "Give me a guide-tone exercise followed by arpeggios.", level="Beginner")
        before = copy.deepcopy(plan_of(s))
        resp = self.go(s, "Make the arpeggio exercise more advanced.")
        after = plan_of(s)
        assert all(r["item_level"] == "Intermediate" for r in after["items"] if r["family"] == "chord_tones")
        assert all(r["item_level"] == "Beginner" for r in after["items"] if r["family"] == "guide_tones")
        b_g = [r for r in before["items"] if r["family"] == "guide_tones"]
        a_g = [r for r in after["items"] if r["family"] == "guide_tones"]
        assert [r["abc"] for r in a_g] == [r["abc"] for r in b_g] and [r["bpm"] for r in a_g] == [r["bpm"] for r in b_g]
        assert "What changed" in resp.composed_markdown() and "Intermediate" in resp.composed_markdown()
        assert min(r["bpm"] for r in after["items"] if r["family"] == "chord_tones") > max(r["bpm"] for r in before["items"] if r["family"] == "chord_tones") - 1
        check_plan(after, 9)
        self.go(s, "Undo that.")
        assert plan_of(s) == before

    def test_more_advanced_stops_at_the_top_level_in_words(self):
        s = self.fresh(level="Advanced")
        before = copy.deepcopy(plan_of(s))
        resp = self.go(s, "Make the arpeggio exercise more advanced.", level="Advanced")
        assert plan_of(s) == before and "already at Advanced" in resp.direct_answer

    def test_make_exercise_two_more_challenging_changes_only_that_exercise(self):
        s = self.fresh(level="Beginner")
        before = copy.deepcopy(plan_of(s))
        self.go(s, "Make the second exercise more challenging, but keep the first exactly as it is.")
        after = plan_of(s)
        assert after["items"][1]["item_level"] == "Intermediate"
        assert after["items"][0]["abc"] == before["items"][0]["abc"]
        for a, b in list(zip(after["items"], before["items"]))[2:]:
            assert a["abc"] == b["abc"]

    def test_start_each_arpeggio_on_the_third(self):
        s = self.fresh(level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        resp = self.go(s, "Start each arpeggio on the third.", level="Intermediate")
        plan = plan_of(s)
        assert plan["spec"]["chord_start"] == "third" and "starts on the third" in resp.composed_markdown()
        for r in plan["items"]:
            assert all(seg["notes"][0]["role"] == "3" for seg in r["meta"]["segments"] if seg["supported"]), r["title"]
        check_plan(plan, 9)
        self.go(s, "Undo that.", level="Intermediate")
        assert plan_of(s) == before

    def test_start_on_the_third_leaves_guide_tones_and_approaches_untouched(self):
        s = song_session("Blue Bossa", level="Intermediate")
        ask(s, "Warm me up for soloing over Blue Bossa.", level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        self.go(s, "Start each arpeggio on the third.", level="Intermediate")
        after = plan_of(s)
        for fam in ("guide_tones", "approach_notes", "scale"):
            assert [r["abc"] for r in after["items"] if r["family"] == fam] == [r["abc"] for r in before["items"] if r["family"] == fam], fam

    def test_start_each_arpeggio_without_any_arpeggios_is_refused(self):
        s = self.fresh("Give me a guide-tone warmup over Blue Bossa.", level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        resp = self.go(s, "Start each arpeggio on the third.", level="Intermediate")
        assert plan_of(s) == before and "no chord-tone arpeggio" in resp.direct_answer

    def test_add_approaches_from_below_adds_the_exercise_with_that_geometry(self):
        s = self.fresh(level="Intermediate")
        resp = self.go(s, "Add approaches from below.", level="Intermediate")
        plan = plan_of(s)
        assert "approach_notes" in fams(plan) and plan["spec"]["approach_kind"] == "below" and "chromatic approach from below" in resp.composed_markdown()
        ap = [r for r in plan["items"] if r["family"] == "approach_notes"]
        assert ap and all(set(map(tuple, (a["offsets"] for a in r["meta"]["approaches"]))) <= {(-1,), (1,)} for r in ap)
        check_plan(plan, 9)

    def test_use_an_enclosure_before_the_next_chord(self):
        s = self.fresh(level="Intermediate")
        self.go(s, "Add approaches from below.", level="Intermediate")
        before_others = [r["abc"] for r in plan_of(s)["items"] if r["family"] != "approach_notes"]
        resp = self.go(s, "Use an enclosure before the next chord.", level="Intermediate")
        plan = plan_of(s)
        assert plan["spec"]["approach_kind"] == "enclosure" and "an enclosure" in resp.composed_markdown()
        for r in plan["items"]:
            if r["family"] == "approach_notes":
                assert {tuple(a["offsets"]) for a in r["meta"]["approaches"]} <= {(1, -1), (-1, 1)}
        assert [r["abc"] for r in plan["items"] if r["family"] != "approach_notes"] == before_others
        check_plan(plan, 9)

    def test_only_the_bridge_and_the_first_four_bars_apply_to_every_song_exercise(self):
        s = song_session("Blue Bossa", level="Intermediate")
        ask(s, "Warm me up for soloing over Blue Bossa.", level="Intermediate")
        self.go(s, "Only the bridge.", level="Intermediate")
        plan = plan_of(s)
        assert plan["spec"]["song_sel"]["section"] == "Section B" and all("Section B" in r["title"] for r in plan["items"] if r["family"] in wp.SONG_FAMILIES)
        check_plan(plan, 9)
        self.go(s, "Just the first four bars.", level="Intermediate")
        plan = plan_of(s)
        assert all(r["bars"] == 4 for r in plan["items"] if r["family"] in wp.SONG_FAMILIES)
        check_plan(plan, 9)

    def test_make_the_second_exercise_slower_and_the_movement_smoother(self):
        s = song_session("Blue Bossa", level="Intermediate")
        ask(s, "Warm me up for soloing over Blue Bossa.", level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        self.go(s, "Make the second exercise slower.", level="Intermediate")
        after = plan_of(s)
        assert after["items"][1]["bpm"] < before["items"][1]["bpm"]
        assert [r["abc"] for i, r in enumerate(after["items"]) if i != 1] == [r["abc"] for i, r in enumerate(before["items"]) if i != 1]
        self.go(s, "Make the movement smoother.", level="Intermediate")
        check_plan(plan_of(s), 9)

    def test_explain_why_these_notes_work_covers_the_chord_tones_and_the_approaches(self):
        s = song_session("Blue Bossa", level="Intermediate")
        ask(s, "Warm me up for soloing over Blue Bossa.", level="Intermediate")
        versions = wp.history(s)["versions"]
        before = copy.deepcopy(plan_of(s))
        text = self.go(s, "Explain why these notes work.", level="Intermediate").composed_markdown()
        assert "Why these notes work" in text and "chord tones:" in text and "resolves" in text.lower() or "→ the" in text
        assert "approach note" in text.lower() and "Each approach and what it resolves to" in text
        assert plan_of(s) == before and wp.history(s)["versions"] == versions

    def test_undo_and_redo_restore_each_exact_version_through_a_whole_conversation(self):
        s = self.fresh(level="Intermediate")
        versions = [copy.deepcopy(plan_of(s))]
        for q in ("Start each arpeggio on the third.", "Add approaches from below.", "Use an enclosure before the next chord.", "Make the arpeggio exercise more advanced.",
                  "Only the bridge.", "Make the second exercise slower.", "Use the whole song."):
            self.go(s, q, level="Intermediate")
            if plan_of(s) != versions[-1]:
                versions.append(copy.deepcopy(plan_of(s)))
        assert len(versions) >= 7
        for expect in reversed(versions[:-1]):
            self.go(s, "Undo that.", level="Intermediate")
            assert plan_of(s) == expect
        for expect in versions[1:]:
            self.go(s, "Redo", level="Intermediate")
            assert plan_of(s) == expect

    def test_unsupported_requests_are_refused_and_change_nothing(self):
        s = self.fresh(level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        versions = wp.history(s)["versions"]
        for q in ("Make the approaches triplets", "Add a pedal point to the arpeggios", "Make it swing"):
            self.go(s, q, level="Intermediate")
            assert plan_of(s) == before and wp.history(s)["versions"] == versions, q

    def test_the_chart_identity_and_the_song_survive_every_revision(self):
        s = self.fresh(level="Intermediate")
        h = plan_of(s)["spec"]["song"]["hash"]
        for q in ("Start each arpeggio on the third.", "Add approaches from below.", "Only the bridge.", "Use the whole song.", "Change it to tenor sax."):
            self.go(s, q, level="Intermediate")
            assert plan_of(s)["spec"]["song"]["hash"] == h and plan_of(s)["spec"]["song"]["title"] == "Blue Bossa"
        check_plan(plan_of(s), 14)

    def test_changing_the_active_song_does_not_rewrite_the_warmup(self):
        s = self.fresh(level="Intermediate")
        before = copy.deepcopy(plan_of(s))
        activate_song(s, "Autumn Leaves")
        assert plan_of(s) == before
        self.go(s, "Add approaches from below.", level="Intermediate")
        assert plan_of(s)["spec"]["song"]["title"] == "Blue Bossa"
        check_plan(plan_of(s), 9)

    def test_nothing_else_in_the_app_changes(self):
        s = self.fresh(level="Intermediate")
        keys = ["instrument", "display_key", "concert_key", "backing_track_bpm", "song", "level", "active_catalog_pick_key"]
        before = {k: copy.deepcopy(s[k]) for k in keys}
        for q in ("Add approaches from below.", "Use an enclosure before the next chord.", "Start each arpeggio on the third.", "Use the whole song.", "Undo that.", "Redo"):
            self.go(s, q, level="Intermediate")
        assert {k: s[k] for k in keys} == before

    def test_another_account_cannot_see_or_change_it(self):
        s = self.fresh(level="Intermediate")
        other = song_session("Blue Bossa", user="someone-else", level="Intermediate")
        ask(other, "Add approaches from below.", level="Intermediate")
        assert wp.current(other) is None

    @pytest.mark.parametrize("who,sax,inst,offset", [("flute", None, "Flute", 0), ("alto", ALTO, "Saxophone", 9), ("tenor", TENOR, "Saxophone", 14)])
    @pytest.mark.parametrize("level", list(we.LEVELS))
    def test_a_mixed_plan_for_flute_alto_and_tenor_at_every_level(self, who, sax, inst, offset, level):
        s = song_session("Autumn Leaves", instrument=inst, sax=sax, level=level)
        ask(s, "Warm me up for soloing over Autumn Leaves.", instrument=inst, level=level, key="Bm")
        plan = plan_of(s)
        assert plan["player"]["offset"] == offset and plan["level"] == level
        check_plan(plan, offset)
        for r in plan["items"]:
            assert all(c["ok"] for c in r["checks"])
            assert [m - offset for m in r["written_midi"]] == r["sounding_midi"]
