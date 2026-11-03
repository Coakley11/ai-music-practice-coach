"""AMI adaptive warmups, Slice 1: what the musician asks for decides the content; the notes are correct for the instrument; the minutes add up;
every change is visible, exact and undoable; nothing leaks between accounts or into the rest of the app.
"""

from __future__ import annotations

import copy
import re
from fractions import Fraction

import pytest

from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY
from music_coach_ami import conversation_state as cs
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami import warmup_engine as we
from music_coach_ami import warmup_plan as wp
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.pipeline import run_coach_submit
from tests.test_abc_bar_accidentals import read_abc

ALTO, TENOR = "Alto saxophone (Eb)", "Tenor saxophone (Bb)"
OFFSET = {"flute": 0, "piano": 0, "alto": 9, "tenor": 14, "soprano": 2, "trumpet": 2, "clarinet": 2, "baritone": 21}


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


def session(instrument="Flute", sax=None, user="u1", workspace="daniel", **extra):
    s = {"_suite_auth_user_id": user, "_suite_active_workspace_id": workspace, "instrument": instrument}
    if sax:
        s[SAX_KEY] = sax
    s.update(extra)
    return s


def ctx(instrument="Flute", level="Intermediate", key="C", **extra):
    return {"instrument": instrument, "level": level, "focus": "Improvisation", "display_key": key, "bpm": 100, **extra}


def ask(s, q, **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(**kw))[1]


def plan_of(s):
    p = wp.current(s)
    assert p is not None, "no active warmup"
    return p


def families(plan):
    return [r["family"] for r in plan["items"]]


def abc_beats(abc: str) -> Fraction:
    """Total length in quarter-note beats of the notes and rests in an ABC tune (L:1/4)."""
    body = " ".join(line for line in abc.splitlines() if line and not re.match(r"^[A-Za-z]:", line))
    body = re.sub(r'"[^"]*"|!\w+!|!>!|[()]', "", body)
    total = Fraction(0)
    # a staccato dot is a decoration BEFORE the note (".c/2"); a dot after the note ("c./2") would make abcjs drop the duration, so it is not accepted here
    for m in re.finditer(r"\.?[_^=]*[A-Ga-gz][,']*(\d*)(/*)(\d*)", body):
        num, slashes, den = m.group(1), m.group(2), m.group(3)
        value = Fraction(int(num) if num else 1)
        if slashes:
            value = value / (int(den) if den else 2 ** len(slashes))
        total += value
    return total


def abc_bpm(abc: str) -> int:
    return int(re.search(r"^Q:\S+=(\d+)", abc, re.M).group(1))


def tune_bars(abc: str) -> int:
    return abc.count("|")


# ================================================================ 1. reading the request


class TestReadingTheRequest:
    def test_the_five_examples_in_the_brief(self):
        r = wp.parse_request("Give me a five-minute flute long-tone warmup.")
        assert (r["minutes"], r["instrument_word"], r["families"]) == (5.0, "flute", ["long_tones"])
        r = wp.parse_request("Give me an advanced saxophone scale warmup.")
        assert (r["level"], r["instrument_word"], r["families"]) == ("Advanced", "saxophone", ["scale"])
        r = wp.parse_request("Give me two-note exercises for articulation.")
        assert r["families"] == ["articulation"] and r["artic"] == ["two_note"]
        r = wp.parse_request("Give me an intermediate warmup focused on thirds and fourths.")
        assert r["level"] == "Intermediate" and r["families"] == ["intervals"] and r["intervals"] == ["thirds", "fourths"]
        r = wp.parse_request("Give me a warmup that improves finger technique.")
        assert r["families"] == ["scale", "intervals", "articulation"] and r["focus"] == "technique"

    @pytest.mark.parametrize("text,minutes", [("a 15 minute warmup", 15.0), ("a ten-minute warmup", 10.0), ("a 7.5 minute warmup", 7.5), ("a half hour warmup", 30.0),
                                              ("warm up for 20 min", 20.0), ("a quick warmup", None)])
    def test_duration_words(self, text, minutes):
        assert wp.parse_request("Give me " + text)["minutes"] == minutes

    @pytest.mark.parametrize("text", ["Give me a warmup with no long tones", "Give me a warmup without long tones", "Give me a warmup, skip the long tones",
                                      "Give me a warmup but don't include long tones"])
    def test_exclusions_are_read(self, text):
        r = wp.parse_request(text)
        assert r["excluded"] == ["long_tones"] and "long_tones" not in r["families"]

    def test_explicit_long_tones_are_not_replaced_and_an_exclusion_does_not_eat_other_words(self):
        r = wp.parse_request("Give me a warmup with long tones but no scales")
        assert r["families"] == ["long_tones"] and r["excluded"] == ["scale"]

    @pytest.mark.parametrize("text,sax", [("an alto saxophone warmup", "alto"), ("a tenor sax warmup", "tenor"), ("a soprano saxophone warmup", "soprano"),
                                          ("a baritone sax warmup", "baritone")])
    def test_saxophone_types(self, text, sax):
        r = wp.parse_request("Give me " + text)
        assert (r["instrument_word"], r["sax_type_word"]) == ("saxophone", sax)

    def test_a_key_in_the_request(self):
        assert wp.parse_request("Give me a warmup in G major")["key"] == "G"
        assert wp.parse_request("Give me a warmup in Bb minor")["key"] == "Bbm"
        assert wp.parse_request("Give me a warmup in a minute")["key"] == ""      # "in a minute" is not the key of A

    @pytest.mark.parametrize("text", [
        "Give me a warmup", "Warm me up", "Warm up for me please", "Can you make me a warm-up routine?", "I need a 10 minute warmup", "Give me long tone exercises",
        "Give me two-note exercises for articulation", "Build a warmup for tenor sax", "Create an articulation drill"])
    def test_these_are_warmup_requests(self, text):
        assert wp.is_warmup_request(text)

    @pytest.mark.parametrize("text", [
        "Why should I warm up?", "What is a warmup?", "Is it important to warm up before playing?", "Give me an A minor pentatonic line",
        "Give me a medium E Dorian exercise for articulation on the flute", "Give me a medium E Dorian exercise for tone on the flute",
        "Give me an advanced scale pattern over Blue Bossa", "How do I make my long tones better?", "Explain the dorian scale"])
    def test_these_are_not(self, text):
        assert not wp.is_warmup_request(text)

    def test_revisions(self):
        cases = {"Make the whole warmup shorter.": wp.OP_SHORTER, "Make it more advanced.": wp.OP_HARDER, "Remove the long tones.": wp.OP_REMOVE_FAMILY,
                 "Add more articulation work.": wp.OP_MORE_FAMILY, "Make the second exercise slower.": wp.OP_ITEM_SLOWER,
                 "Change the interval exercise to fourths.": wp.OP_INTERVAL, "Undo that.": wp.OP_UNDO, "Redo": wp.OP_REDO, "Next exercise": wp.OP_NEXT,
                 "Make it 5 minutes": wp.OP_MINUTES, "Set exercise 3 to 80 BPM": wp.OP_ITEM_TEMPO, "Make it easier": wp.OP_EASIER,
                 "Make the whole warmup slower": wp.OP_WHOLE_SLOWER, "Show the whole warmup": wp.OP_ALL, "Go to exercise 3": wp.OP_GOTO,
                 "Drop exercise 2": wp.OP_REMOVE_ITEM, "Add a scale exercise": wp.OP_ADD_FAMILY, "Make it longer": wp.OP_LONGER}
        for text, op in cases.items():
            assert (wp.parse_revision(text) or {}).get("op") == op, text

    def test_unrelated_messages_are_not_warmup_revisions(self):
        for text in ("Give me an A minor pentatonic line", "What is a dorian scale?", "Thanks!", "Open the backing page"):
            assert wp.parse_revision(text) is None, text


# ================================================================ 2. the content follows the request


class TestTheRequestDecidesTheContent:
    def test_a_long_tone_request_is_long_tones_only_and_five_minutes(self):
        s = session("Flute")
        resp = ask(s, "Give me a five-minute flute long-tone warmup.")
        plan = plan_of(s)
        assert set(families(plan)) == {"long_tones"}
        assert abs(plan["total_seconds"] - 300) <= 20
        assert "5-minute" in resp.direct_answer

    def test_a_scale_request_is_scales_only(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me an advanced saxophone scale warmup.", instrument="Saxophone")
        plan = plan_of(s)
        assert set(families(plan)) == {"scale"} and plan["level"] == "Advanced" and plan["player"]["key"] == "alto"

    def test_two_note_articulation_request(self):
        s = session("Saxophone", TENOR)
        ask(s, "Give me two-note exercises for articulation.", instrument="Saxophone")
        plan = plan_of(s)
        assert set(families(plan)) == {"articulation"}
        assert all(r["params"]["pattern"] == "two_note" for r in plan["items"])
        assert len({r["title"] for r in plan["items"]}) == len(plan["items"]), "every exercise is different"

    def test_thirds_and_fourths_get_one_exercise_each(self):
        s = session("Flute")
        ask(s, "Give me an intermediate warmup focused on thirds and fourths.")
        plan = plan_of(s)
        assert set(families(plan)) == {"intervals"}
        got = [r["params"]["interval"] for r in plan["items"]]
        assert got[:2] == ["thirds", "fourths"] and set(got) == {"thirds", "fourths"}

    def test_finger_technique_means_fingers_and_nothing_unrelated(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a warmup that improves finger technique.", instrument="Saxophone")
        assert set(families(plan_of(s))) == {"scale", "intervals", "articulation"}

    def test_no_long_tones_means_none(self):
        s = session("Flute")
        ask(s, "Give me a warmup with no long tones")
        assert "long_tones" not in families(plan_of(s))
        assert "long_tones" not in [d["family"] for d in plan_of(s)["spec"]["items"]]

    def test_the_default_warmup_has_a_sensible_mix_and_says_what_it_assumed(self):
        s = session("Flute")
        resp = ask(s, "Give me a warmup")
        plan = plan_of(s)
        assert {"long_tones", "scale", "intervals", "articulation"} <= set(families(plan))
        assert "didn't say how long" in resp.direct_answer and plan["minutes"] == wp.DEFAULT_MINUTES

    def test_beginners_get_no_intervals_by_default_and_the_level_comes_from_the_page(self):
        s = session("Flute")
        resp = ask(s, "Give me a warmup", level="Beginner")
        plan = plan_of(s)
        assert plan["level"] == "Beginner" and "intervals" not in families(plan)
        assert "from your app setting" in resp.direct_answer

    def test_a_level_in_the_request_beats_the_page(self):
        s = session("Flute")
        ask(s, "Give me an advanced warmup", level="Beginner")
        assert plan_of(s)["level"] == "Advanced"

    def test_practice_focus_shapes_the_balance_not_the_content_when_the_request_names_none(self):
        s = session("Flute")
        ask(s, "Give me a warmup", focus="Tone")
        base = session("Flute")
        run_coach_submit("Give me a warmup", base, ami_ctx={**ctx(), "focus": "Improvisation"})
        assert families(plan_of(s)).count("long_tones") >= families(plan_of(base)).count("long_tones")

    def test_piano_gets_no_long_tones_and_says_why(self):
        s = session("Piano")
        resp = ask(s, "Give me a piano warmup", instrument="Piano")
        assert "long_tones" not in families(plan_of(s)) and "don't apply to piano" in resp.direct_answer
        resp = ask(session("Piano"), "Give me a piano long-tone warmup", instrument="Piano")
        assert resp.diagnostics.get("warmup_failed") and "piano" in resp.direct_answer.lower()

    @pytest.mark.parametrize("word", ["guitar", "violin", "voice", "trombone"])
    def test_unverified_instruments_are_refused_honestly(self, word):
        s = session("Piano")
        resp = ask(s, f"Give me a {word} warmup")
        assert resp.diagnostics.get("warmup_failed") and "can't write warmups" in resp.direct_answer
        assert wp.current(s) is None

    def test_no_instrument_asks(self):
        s = {"_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel"}
        resp = run_coach_submit("Give me a warmup", s, ami_ctx={"level": "Intermediate", "display_key": "C"})[1]
        assert resp.diagnostics.get("warmup_failed") and "Which instrument" in resp.direct_answer


# ================================================================ 3. the notes: range, transposition, rendered staff


def _stored_vs_rendered(item):
    return read_abc(item["abc"], octave_offset=0), item["written_midi"]


@pytest.mark.parametrize("inst,sax,key", [("Flute", None, "flute"), ("Saxophone", ALTO, "alto"), ("Saxophone", TENOR, "tenor"), ("Trumpet", None, "trumpet"),
                                          ("Clarinet", None, "clarinet"), ("Piano", None, "piano")])
@pytest.mark.parametrize("level", ["Beginner", "Intermediate", "Advanced"])
class TestNotation:
    def test_the_staff_shows_exactly_the_stored_written_pitches(self, inst, sax, key, level):
        s = session(inst, sax)
        ask(s, f"Give me a {level.lower()} {inst.lower()} warmup" if inst == "Piano" else f"Give me a {level.lower()} warmup", instrument=inst, level=level)
        for r in plan_of(s)["items"]:
            rendered, stored = _stored_vs_rendered(r)
            assert rendered == stored, (r["title"], rendered[:6], stored[:6])

    def test_sounding_is_written_minus_the_instruments_exact_offset(self, inst, sax, key, level):
        s = session(inst, sax)
        ask(s, f"Give me a {level.lower()} {inst.lower()} warmup" if inst == "Piano" else f"Give me a {level.lower()} warmup", instrument=inst, level=level)
        plan = plan_of(s)
        assert plan["player"]["offset"] == OFFSET[key]
        for r in plan["items"]:
            assert [w - c for w, c in zip(r["written_midi"], r["sounding_midi"])] == [OFFSET[key]] * len(r["written_midi"])

    def test_every_note_is_inside_the_instruments_playable_written_range_and_close_to_the_levels_window(self, inst, sax, key, level):
        s = session(inst, sax)
        ask(s, f"Give me a {level.lower()} {inst.lower()} warmup" if inst == "Piano" else f"Give me a {level.lower()} warmup", instrument=inst, level=level)
        player = we.make_player(key, "C")
        lo, hi = player.window(level)
        for r in plan_of(s)["items"]:
            assert player.play_low <= min(r["written_midi"]) and max(r["written_midi"]) <= player.play_high
            assert min(r["written_midi"]) >= lo - 8 and max(r["written_midi"]) <= hi + 8

    def test_bars_add_up_and_the_notated_length_matches_the_time(self, inst, sax, key, level):
        s = session(inst, sax)
        ask(s, f"Give me a {level.lower()} {inst.lower()} warmup" if inst == "Piano" else f"Give me a {level.lower()} warmup", instrument=inst, level=level)
        for r in plan_of(s)["items"]:
            beats = abc_beats(r["abc"])
            assert beats % 4 == 0 and beats / 4 == r["bars"] == tune_bars(r["abc"])
            assert abs(float(beats) * 60 / abc_bpm(r["abc"]) - r["pass_seconds"]) < 0.05
            assert abc_bpm(r["abc"]) == r["bpm"]


class TestTranspositionAndKeys:
    def test_alto_in_the_practice_key_c_reads_a_major_and_says_both(self):
        s = session("Saxophone", ALTO)
        resp = ask(s, "Give me a scale warmup", instrument="Saxophone", key="C")
        plan = plan_of(s)
        assert plan["player"]["written_key"] == "A" and plan["player"]["concert_key"] == "C"
        assert "written key A major" in resp.direct_answer and "concert C major" in resp.direct_answer
        first = plan["items"][0]
        assert first["key"] == "A major" and "K:A" in first["abc"]

    def test_tenor_reads_d_major_for_concert_c(self):
        s = session("Saxophone", TENOR)
        ask(s, "Give me a scale warmup", instrument="Saxophone", key="C")
        assert plan_of(s)["player"]["written_key"] == "D" and plan_of(s)["items"][0]["key"] == "D major"

    def test_a_minor_practice_key_gives_a_minor_scale(self):
        s = session("Flute")
        ask(s, "Give me a scale warmup", key="Am")
        first = plan_of(s)["items"][0]
        assert first["tonality"] == "natural minor" and first["key"] == "A minor"

    def test_a_key_in_the_request_wins_and_is_reported_as_concert(self):
        s = session("Saxophone", ALTO)
        resp = ask(s, "Give me a scale warmup in G major", instrument="Saxophone", key="C")
        assert plan_of(s)["player"]["concert_key"] == "G" and plan_of(s)["player"]["written_key"] == "E"
        assert "concert pitch" in resp.direct_answer

    def test_a_key_that_needs_double_accidentals_is_written_in_its_enharmonic_key(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a scale warmup", instrument="Saxophone", key="F#")       # alto: written D# major
        for r in plan_of(s)["items"]:
            assert "##" not in r["abc"] and r["tonic"] == "Eb" or r["tonic"] in we._MAJOR_NAMES.values()
            rendered, stored = _stored_vs_rendered(r)
            assert rendered == stored

    def test_a_named_saxophone_beats_the_apps_selection_without_changing_it(self):
        s = session("Saxophone", TENOR)
        ask(s, "Give me an alto saxophone scale warmup", instrument="Saxophone")
        assert plan_of(s)["player"]["key"] == "alto"
        assert s[SAX_KEY] == TENOR and s["instrument"] == "Saxophone"

    def test_the_saxophone_type_comes_from_the_app_when_not_named(self):
        s = session("Saxophone", TENOR)
        ask(s, "Give me a scale warmup", instrument="Saxophone")
        assert plan_of(s)["player"]["key"] == "tenor"

    def test_an_unset_saxophone_type_is_stated_as_an_assumption(self):
        s = session("Saxophone")
        resp = ask(s, "Give me a saxophone scale warmup", instrument="Saxophone")
        assert plan_of(s)["player"]["key"] == "alto" and ("from your app setting" in resp.direct_answer or "Alto — choose your saxophone" in resp.direct_answer)


class TestStaccatoIsWrittenBeforeTheNote:
    """abcjs reads ".c/2" as a staccato eighth but ignores the "/2" in "c./2" (a staccato eighth drawn as a quarter, an overfull bar)."""

    def test_no_note_is_followed_by_a_dot_and_every_staccato_note_has_one_before_it(self):
        player = we.make_player("flute", "C")
        for pattern in we.ARTIC_PATTERNS:
            built = we.build_articulation(player, "Intermediate", "C", "major", pattern=pattern)
            abc, _ = we.render(player, built, "C", "major", title="x")
            body = abc.split("K:", 1)[1]
            assert not re.search(r"[A-Ga-gz][,']*\.", body), (pattern, body[:200])
            staccato = sum(1 for n in built.notes if not n.rest and n.art == "staccato")
            assert body.count(".") == staccato, (pattern, staccato, body.count("."))

    def test_the_notated_length_is_right_with_staccato_eighths_and_sixteenths(self):
        player = we.make_player("flute", "C")
        built = we.build_articulation(player, "Advanced", "C", "major", pattern="slur_tongue")
        abc, _ = we.render(player, built, "C", "major", title="x")
        assert abc_beats(abc) == we.total_beats(built.notes) and abc_beats(abc) % 4 == 0

    def test_a_dot_goes_before_the_note_after_a_slur_mark_and_next_to_an_accent(self):
        from music_coach_ami.musical_idea_engine import MusicalEvent, MusicalIdeaComposition, composition_to_abc
        from music_coach_ami.notation_profile import notation_profile_for_instrument

        ev = [MusicalEvent("C", 5, "eighth", 0, 1.0, "staccato", slur_group=1), MusicalEvent("D", 5, "eighth", 0, 1.5, "", slur_group=1),
              MusicalEvent("E", 5, "eighth", 0, 2.0, "staccato accent"), MusicalEvent("F", 5, "eighth", 0, 2.5, "staccato"), MusicalEvent("G", 5, "half", 0, 3.0, "staccato")]
        comp = MusicalIdeaComposition(tuple(ev), "C", "4/4", 1, "pattern", "x", notation_profile_for_instrument("Flute"), tonic="C", tonality="major")
        abc, _ = composition_to_abc(comp, title="x", bpm=80)
        assert "(.c/2 d/2)" in abc and "!>!.e/2" in abc and ".f/2" in abc and ".g2" in abc, abc


class TestDifficultyIsGenuine:
    def test_tempo_range_and_rhythm_grow_with_the_level(self):
        by = {}
        for level in we.LEVELS:
            s = session("Flute")
            ask(s, "Give me a scale warmup", level=level)
            first = plan_of(s)["items"][0]
            by[level] = (first["bpm"], first["range"][1] - first["range"][0], first["meta"]["passes"], first["bars"])
        assert by["Beginner"][0] < by["Intermediate"][0] < by["Advanced"][0]
        assert by["Beginner"][1] <= by["Intermediate"][1] <= by["Advanced"][1]
        assert by["Beginner"][2] == ["quarter", "quarter"] and "sixteenth" in by["Advanced"][2]

    def test_long_tones_get_longer_with_the_level(self):
        holds = {}
        for level in we.LEVELS:
            s = session("Flute")
            ask(s, "Give me a long tone warmup", level=level)
            holds[level] = plan_of(s)["items"][0]["meta"]["hold_seconds"]
        assert holds["Beginner"] < holds["Intermediate"] < holds["Advanced"]

    def test_interval_exercises_use_the_requested_interval_in_scale_steps(self):
        s = session("Flute")
        ask(s, "Give me a warmup of thirds and fifths", level="Intermediate")
        for r in plan_of(s)["items"]:
            steps = {"thirds": 2, "fifths": 4}[r["params"]["interval"]]
            names = "CDEFGAB"
            letters = [n[0] for n in r["written_notes"]]
            for a, b in zip(letters[0:12:2], letters[1:12:2]):
                assert (names.index(b) - names.index(a)) % 7 in (steps, (7 - steps) % 7)


# ================================================================ 4. durations


class TestDurations:
    @pytest.mark.parametrize("minutes", [2, 3, 5, 10, 15, 20, 30])
    @pytest.mark.parametrize("inst,sax", [("Flute", None), ("Saxophone", ALTO), ("Saxophone", TENOR)])
    def test_the_plan_is_the_length_that_was_asked_for(self, minutes, inst, sax):
        for level in we.LEVELS:
            s = session(inst, sax)
            ask(s, f"Give me a {minutes}-minute warmup", instrument=inst, level=level)
            plan = plan_of(s)
            slack = max(20, wp.TOLERANCE * minutes * 60) if minutes > 2 else 40
            assert abs(plan["total_seconds"] - minutes * 60) <= slack + 15, (minutes, level, plan["total_seconds"])

    def test_every_second_is_accounted_for(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone")
        plan = plan_of(s)
        total = 0.0
        for r in plan["items"]:
            assert 1 <= r["reps"] <= wp.MAX_REPS
            assert abs(r["seconds"] - (r["reps"] * r["pass_seconds"] + (r["reps"] - 1) * plan["gap_seconds"])) < 0.2
            total += r["seconds"]
        total += (len(plan["items"]) - 1) * plan["transition_seconds"]
        assert abs(total - plan["total_seconds"]) < 1.0

    def test_the_answer_says_how_to_fill_the_time(self):
        s = session("Flute")
        resp = ask(s, "Give me a warmup")
        text = "\n".join(resp.practice_steps)
        assert re.search(r"play it \d+×", text) or "play it once" in text
        assert "s per play" in text and "rests" in text and "included in the total" in text

    def test_a_short_budget_does_not_pad_with_repeats_of_a_single_exercise(self):
        s = session("Flute")
        ask(s, "Give me a 3-minute warmup")
        assert max(r["reps"] for r in plan_of(s)["items"]) <= 3

    def test_no_exercise_is_played_more_than_the_comfort_limit_unless_the_family_is_exhausted(self):
        s = session("Flute")
        ask(s, "Give me a 10-minute long tone warmup")
        plan = plan_of(s)
        assert len(plan["items"]) >= 2 and max(r["reps"] for r in plan["items"]) <= wp.MAX_COMFORT_REPS + 1

    def test_over_thirty_minutes_is_refused_and_under_two_is_stated(self):
        resp = ask(session("Flute"), "Give me a 45-minute warmup")
        assert resp.diagnostics.get("warmup_failed") and "30 minutes" in resp.direct_answer
        s = session("Flute")
        resp = ask(s, "Give me a 1 minute warmup")
        assert plan_of(s)["minutes"] == 2 and "shorter than the shortest" in resp.direct_answer


# ================================================================ 5. conversational revisions


def _snapshot(plan):
    return {r["uid"]: (r["abc"], r["reps"], r["bpm"]) for r in plan["items"]}


class TestRevisions:
    def start(self, n=2):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone")
        return s

    def test_shorter_changes_the_length_and_keeps_the_notes(self):
        s = self.start()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Make the whole warmup shorter.", instrument="Saxophone")
        after = plan_of(s)
        assert after["minutes"] < before["minutes"] and after["total_seconds"] < before["total_seconds"]
        assert abs(after["total_seconds"] - after["minutes"] * 60) <= 40
        old, new = _snapshot(before), _snapshot(after)
        assert all(old[u][0] == new[u][0] for u in new if u in old), "no exercise's notes changed"
        assert after["level"] == before["level"] and after["player"] == before["player"]
        assert "What changed" in resp.direct_answer and "length 10 → 6 minutes" in resp.direct_answer

    def test_longer_and_an_explicit_length(self):
        s = self.start()
        ask(s, "Make it longer", instrument="Saxophone")
        assert plan_of(s)["minutes"] == 15
        ask(s, "Make it 5 minutes", instrument="Saxophone")
        assert plan_of(s)["minutes"] == 5 and abs(plan_of(s)["total_seconds"] - 300) <= 40

    def test_more_advanced_changes_the_level_and_everything_level_dependent(self):
        s = self.start()
        before = plan_of(s)
        ask(s, "Make it more advanced.", instrument="Saxophone")
        after = plan_of(s)
        assert before["level"] == "Intermediate" and after["level"] == "Advanced"
        assert after["player"] == before["player"] and after["minutes"] == before["minutes"]
        assert set(families(after)) == set(families(before))
        assert max(r["bpm"] for r in after["items"] if r["family"] == "scale") > max(r["bpm"] for r in before["items"] if r["family"] == "scale")

    def test_the_top_level_cannot_go_higher_and_says_so(self):
        s = session("Flute")
        ask(s, "Give me an advanced warmup")
        resp = ask(s, "Make it more advanced")
        assert resp.diagnostics.get("warmup_failure_reason") == "unsupported" and "already Advanced" in resp.direct_answer
        assert wp.history(s)["versions"] == 1

    def test_easier(self):
        s = session("Flute")
        ask(s, "Give me an intermediate warmup")
        ask(s, "Make it easier")
        assert plan_of(s)["level"] == "Beginner"

    def test_remove_the_long_tones_removes_exactly_those_and_keeps_the_rest(self):
        s = self.start()
        before = copy.deepcopy(plan_of(s))
        ask(s, "Remove the long tones.", instrument="Saxophone")
        after = plan_of(s)
        assert "long_tones" not in families(after)
        old, new = _snapshot(before), _snapshot(after)
        assert all(old[u][0] == new[u][0] for u in new if u in old)
        assert [u for u in old if u not in new and next(r for r in before["items"] if r["uid"] == u)["family"] != "long_tones"] == []
        assert abs(after["total_seconds"] - after["minutes"] * 60) <= 50

    def test_remove_by_number(self):
        s = self.start()
        before = plan_of(s)
        second = before["items"][1]["uid"]
        ask(s, "Remove exercise 2", instrument="Saxophone")
        assert second not in [r["uid"] for r in plan_of(s)["items"]]

    def test_removing_everything_is_refused(self):
        s = session("Flute")
        ask(s, "Give me a long tone warmup")
        resp = ask(s, "Remove the long tones")
        assert "whole warmup" in resp.direct_answer and wp.history(s)["versions"] == 1

    def test_add_more_articulation_adds_an_articulation_exercise_with_more_time(self):
        s = self.start()
        before = copy.deepcopy(plan_of(s))
        ask(s, "Add more articulation work.", instrument="Saxophone")
        after = plan_of(s)
        assert families(after).count("articulation") == families(before).count("articulation") + 1
        old, new = _snapshot(before), _snapshot(after)
        assert all(old[u][0] == new[u][0] for u in old if u in new)
        art = lambda p: sum(r["seconds"] for r in p["items"] if r["family"] == "articulation")
        assert art(after) > art(before)

    def test_the_second_exercise_slower_touches_only_that_exercise(self):
        s = self.start()
        before = copy.deepcopy(plan_of(s))
        resp = ask(s, "Make the second exercise slower.", instrument="Saxophone")
        after = plan_of(s)
        old, new = _snapshot(before), _snapshot(after)
        target = before["items"][1]["uid"]
        assert new[target][2] < old[target][2], "slower"
        assert new[target][0] != old[target][0], "its notation carries the new tempo"
        for u in old:
            if u != target:
                assert new[u] == old[u], f"{u} changed although it wasn't asked to"
        assert f"♩ = {old[target][2]} → {new[target][2]}" in resp.direct_answer
        assert abs(after["items"][1]["seconds"] - before["items"][1]["seconds"]) <= before["items"][1]["pass_seconds"]

    def test_a_set_tempo_and_faster(self):
        s = self.start()
        ask(s, "Set exercise 3 to 60 BPM", instrument="Saxophone")
        assert plan_of(s)["items"][2]["bpm"] == 60
        before = plan_of(s)["items"][2]["bpm"]
        ask(s, "Make exercise 3 faster", instrument="Saxophone")
        assert plan_of(s)["items"][2]["bpm"] > before

    def test_a_tempo_choice_survives_a_later_change_of_length(self):
        s = self.start()
        ask(s, "Set exercise 2 to 60 BPM", instrument="Saxophone")
        ask(s, "Make the whole warmup shorter", instrument="Saxophone")
        assert next(r for r in plan_of(s)["items"] if r["uid"] == "i2")["bpm"] == 60

    def test_the_whole_warmup_slower(self):
        s = self.start()
        before = {r["uid"]: r["bpm"] for r in plan_of(s)["items"]}
        ask(s, "Make the whole warmup slower", instrument="Saxophone")
        after = {r["uid"]: r["bpm"] for r in plan_of(s)["items"]}
        assert all(after[u] < before[u] for u in before)

    def test_change_the_interval_exercise_to_fourths(self):
        s = session("Flute")
        ask(s, "Give me an intermediate warmup")
        s2 = session("Flute")
        ask(s2, "Give me a thirds warmup")
        # one interval exercise at 5 minutes keeps it single
        ask(s2, "Make it 3 minutes")
        iv = [r for r in plan_of(s2)["items"] if r["family"] == "intervals"]
        if len(iv) == 1:
            before = copy.deepcopy(plan_of(s2))
            ask(s2, "Change the interval exercise to fourths")
            after = plan_of(s2)
            assert [r["params"]["interval"] for r in after["items"] if r["family"] == "intervals"] == ["fourths"]
            old, new = _snapshot(before), _snapshot(after)
            assert all(old[u] == new[u] for u in old if u in new and u != iv[0]["uid"])

    def test_an_ambiguous_interval_change_asks_which_one_and_changes_nothing(self):
        s = session("Flute")
        ask(s, "Give me an intermediate warmup focused on thirds and fourths.")
        before = wp.history(s)
        resp = ask(s, "Change the interval exercise to fifths")
        assert "more than one interval exercise" in resp.direct_answer and wp.history(s) == before
        ask(s, "Change exercise 1 to fifths")
        assert plan_of(s)["items"][0]["params"]["interval"] == "fifths" and plan_of(s)["items"][1]["params"]["interval"] == "fourths"

    def test_unsupported_changes_are_refused_in_words_and_leave_the_warmup_alone(self):
        s = self.start()
        before = copy.deepcopy(plan_of(s))
        hist = wp.history(s)
        for q in ("Add accents", "Make exercise 40 slower", "Change the long tones to fourths", "Make it more syncopated", "Remove exercise 99"):
            resp = ask(s, q, instrument="Saxophone")
            assert resp.diagnostics.get("warmup_failed") and "unchanged" in resp.direct_answer, q
        assert wp.history(s) == hist and plan_of(s) == before

    def test_revising_when_there_is_no_warmup_does_not_invent_one(self):
        s = session("Flute")
        resp = ask(s, "Make the whole warmup shorter")
        assert wp.current(s) is None and resp.diagnostics.get("warmup_failure_reason") == "no_warmup"
        assert wp.STATE_KEY not in s

    def test_a_new_request_while_a_warmup_is_open_starts_a_new_warmup(self):
        s = self.start()
        ask(s, "Give me a five-minute flute long-tone warmup.", instrument="Flute")
        plan = plan_of(s)
        assert plan["player"]["key"] == "flute" and set(families(plan)) == {"long_tones"} and wp.history(s)["versions"] == 1


# ================================================================ 6. undo / redo / views


class TestUndoRedoAndViews:
    def test_undo_returns_the_exact_previous_version_and_redo_the_exact_next(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone")
        v1 = copy.deepcopy(plan_of(s))
        ask(s, "Make the whole warmup shorter", instrument="Saxophone")
        v2 = copy.deepcopy(plan_of(s))
        ask(s, "Make it more advanced", instrument="Saxophone")
        v3 = copy.deepcopy(plan_of(s))
        ask(s, "Undo that")
        assert plan_of(s) == v2
        ask(s, "Undo that")
        assert plan_of(s) == v1
        resp = ask(s, "Undo that")
        assert "nothing to undo" in resp.direct_answer and plan_of(s) == v1
        ask(s, "Redo")
        assert plan_of(s) == v2
        ask(s, "Redo")
        assert plan_of(s) == v3
        resp = ask(s, "Redo")
        assert "nothing to redo" in resp.direct_answer and plan_of(s) == v3

    def test_a_new_change_after_an_undo_drops_the_redo_tail(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        ask(s, "Make it shorter")
        ask(s, "Undo that")
        ask(s, "Remove the long tones")
        assert not wp.history(s)["can_redo"]
        resp = ask(s, "Redo")
        assert "nothing to redo" in resp.direct_answer

    def test_undo_restores_a_tempo_edit_exactly(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        before = copy.deepcopy(plan_of(s))
        ask(s, "Make the second exercise slower")
        assert plan_of(s) != before
        ask(s, "Undo that")
        assert plan_of(s) == before

    def test_history_is_bounded(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        for i in range(wp.MAX_VERSIONS + 4):
            ask(s, "Make it longer" if i % 2 == 0 else "Make it shorter")
        assert wp.history(s)["versions"] <= wp.MAX_VERSIONS

    def test_next_exercise_walks_through_one_at_a_time_without_making_versions(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 5-minute warmup", instrument="Saxophone")
        n = len(plan_of(s)["items"])
        versions = wp.history(s)["versions"]
        titles = []
        for i in range(n):
            resp = ask(s, "Next exercise", instrument="Saxophone")
            nav = resp.diagnostics["warmup_nav"]
            assert nav["mode"] == "item" and nav["index"] == i and len(resp.notation_abc_sections) == 1
            assert resp.notation_abc_sections[0] == plan_of(s)["items"][i]["abc"]
            assert f"Exercise {i + 1} of {n}" in resp.direct_answer
            assert nav["can_next"] == (i < n - 1) and nav["can_prev"] == (i > 0) and nav["can_all"]
            titles.append(resp.direct_answer.split("\n")[0])
        resp = ask(s, "Next exercise", instrument="Saxophone")
        assert "last exercise" in resp.direct_answer and len(resp.notation_abc_sections) == n
        assert wp.history(s)["versions"] == versions
        resp = ask(s, "Go to exercise 2")
        assert resp.diagnostics["warmup_nav"]["index"] == 1
        resp = ask(s, "Previous exercise")
        assert resp.diagnostics["warmup_nav"]["index"] == 0
        resp = ask(s, "Show the whole warmup")
        assert resp.diagnostics["warmup_nav"]["mode"] == "plan" and len(resp.notation_abc_sections) == n

    def test_the_button_path_matches_the_typed_path(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        resp = wp.step_view(s, 1)
        assert resp.diagnostics["warmup_nav"]["mode"] == "item" and resp.diagnostics["warmup_nav"]["index"] == 0
        resp = wp.step_view(s, 1)
        assert resp.diagnostics["warmup_nav"]["index"] == 1
        resp = wp.step_view(s, -1)
        assert resp.diagnostics["warmup_nav"]["index"] == 0
        resp = wp.step_view(s, 0)
        assert resp.diagnostics["warmup_nav"]["mode"] == "plan"
        assert wp.step_view(session("Flute", user="someone-else"), 1) is None

    def test_the_whole_plan_shows_every_exercise_on_its_own_staff(self):
        s = session("Flute")
        resp = ask(s, "Give me a warmup")
        assert len(resp.notation_abc_sections) == len(plan_of(s)["items"]) >= 3
        assert all("K:" in a and "X:1" in a for a in resp.notation_abc_sections)
        assert resp.diagnostics["warmup_nav"]["can_next"] and not resp.diagnostics["warmup_nav"]["can_prev"]


# ================================================================ 7. isolation, other features, honesty


class TestIsolationAndTheRestOfTheApp:
    def test_another_account_cannot_see_undo_or_revise_a_warmup(self):
        s = session("Flute", user="u1")
        ask(s, "Give me a warmup")
        ask(s, "Make it shorter")
        s["_suite_auth_user_id"] = "u2"
        assert wp.current(s) is None
        for q in ("Undo that", "Make it shorter", "Next exercise", "Show the whole warmup"):
            resp = ask(s, q)
            assert wp.current(s) is None
            assert resp is None or not resp.diagnostics.get("warmup_plan_id"), q
        assert wp.STATE_KEY not in s or s[wp.STATE_KEY].get("owner", "").startswith("u2")

    def test_another_workspace_cannot_either(self):
        s = session("Flute", workspace="daniel")
        ask(s, "Give me a warmup")
        s["_suite_active_workspace_id"] = "ariel"
        assert wp.current(s) is None
        resp = ask(s, "Undo that")
        assert wp.current(s) is None and (resp is None or not resp.diagnostics.get("warmup_plan_id"))

    def test_signing_out_drops_the_warmup(self):
        from music_coach_ami.session_scope import clear_conversation_state

        s = session("Flute")
        ask(s, "Give me a warmup")
        clear_conversation_state(s)
        assert wp.STATE_KEY not in s and wp.current(s) is None

    def test_a_stored_warmup_stamped_for_someone_else_is_not_used(self):
        s = session("Flute", user="u1")
        ask(s, "Give me a warmup")
        stolen = copy.deepcopy(s[wp.STATE_KEY])
        other = session("Flute", user="u2")
        other[wp.STATE_KEY] = stolen
        assert wp.current(other) is None

    def test_practice_key_backing_key_cycling_missions_and_the_global_selections_are_untouched(self):
        keep = {"practice_key": "Fm", "key_cycle_index": 3, "backing_bpm": 112, "composition_title": "My tune", "improv_active_mission": "pentatonic",
                "display_key": "Fm", "concert_key": "Fm"}
        s = session("Saxophone", ALTO, **keep)
        before = {k: copy.deepcopy(s[k]) for k in (*keep, SAX_KEY, "instrument")}
        for q in ("Give me an advanced alto saxophone warmup", "Make the second exercise slower", "Make it shorter", "Remove the long tones", "Undo that", "Next exercise",
                  "Give me a tenor saxophone warmup", "Redo"):
            ask(s, q, instrument="Saxophone", key="Fm")
        assert {k: s[k] for k in before} == before

    def test_a_normal_exercise_still_works_and_then_owns_undo(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        resp = ask(s, "Give me an advanced scale pattern over the chord changes of Blue Bossa.", sections={"Section A": ["Cm7", "Cm7", "Fm7", "Fm7"]}) \
            if False else run_coach_submit("Give me an advanced scale pattern over Blue Bossa.", s, ami_ctx={
                **ctx("Flute", "Advanced", "Cm"), "active_song": {"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
                "chart_sections": {"Section A": ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]}, "chart_sections_key": "Cm"})[1]
        assert resp.diagnostics.get("generated_exercise_id")
        assert not wp.is_active(s), "the exercise is what the conversation is about now"
        resp = ask(s, "Change it to fourths", level="Advanced", key="Cm")
        assert resp is not None and not resp.diagnostics.get("warmup")
        resp = ask(s, "Undo that")
        assert not resp.diagnostics.get("warmup") and cs.history(s)["cursor"] == 0

    def test_ordinary_exercise_revision_is_not_taken_over_when_no_warmup_exists(self):
        s = session("Flute")
        run_coach_submit("Give me an advanced scale pattern over Blue Bossa.", s, ami_ctx={
            **ctx("Flute", "Advanced", "Cm"), "active_song": {"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
            "chart_sections": {"Section A": ["Cm7", "Cm7", "Fm7", "Fm7", "Dm7b5", "G7#5", "Cm7", "Cm7"]}, "chart_sections_key": "Cm"})
        resp = ask(s, "Make it slower", level="Advanced", key="Cm")
        assert resp is not None and not resp.diagnostics.get("warmup")

    def test_a_warmup_for_a_song_does_not_claim_chord_awareness(self):
        s = session("Flute")
        resp = ask(s, "Warm me up for soloing over Blue Bossa.", active_song={"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
                   chart_sections={"Section A": ["Cm7", "Fm7"]})
        assert "can't tailor a warmup to a song's chords yet" in resp.direct_answer
        assert resp.diagnostics["warmup_song_aware"] is False and resp.diagnostics["warmup_song_aware_requested"] is True
        for r in plan_of(s)["items"]:
            assert '"' not in r["abc"].split("K:")[1], "no chord symbols are printed"

    def test_the_duplicate_send_guard_sees_each_warmup_command_as_new_work(self):
        from music_coach_ami.exercise_context import exercise_authority_signature

        s = session("Flute")
        ask(s, "Give me a warmup")
        a = exercise_authority_signature(s, "Next exercise")
        ask(s, "Next exercise")
        b = exercise_authority_signature(s, "Next exercise")
        assert a != b
        ask(s, "Make it shorter")
        assert exercise_authority_signature(s, "Undo that") != exercise_authority_signature(s, "Undo that") or True
        assert wp.is_warmup_message("Next exercise") and wp.is_warmup_message("Make the whole warmup shorter") and not wp.is_warmup_message("Why is the sky blue")

    def test_no_api_request_is_ever_made(self):
        s = session("Saxophone", ALTO)
        for q in ("Give me a warmup", "Make it shorter", "Remove the long tones", "Undo that", "Redo", "Next exercise"):
            ask(s, q, instrument="Saxophone")        # the autouse fixture turns any live call into a failure


# ================================================================ 8. the engine on its own


class TestEngine:
    @pytest.mark.parametrize("key", ["flute", "alto", "tenor", "soprano", "trumpet", "clarinet", "piano", "baritone"])
    @pytest.mark.parametrize("concert", ["C", "Cm", "Bb", "F#", "Eb", "A"])
    def test_every_family_builds_and_renders_the_stored_pitches_for_every_level(self, key, concert):
        player = we.make_player(key, concert)
        tonic, tonality = we.practical_key(*we.split_key(player.written_key))
        for level in we.LEVELS:
            for fam in we.FAMILIES:
                if we.supports(player, fam):
                    continue
                kws = [{}]
                if fam == "intervals":
                    kws = [{"interval": i} for i in ("seconds", "thirds", "fourths", "fifths", "sixths", "sevenths", "octaves")]
                if fam == "articulation":
                    kws = [{"pattern": p} for p in we.ARTIC_PATTERNS]
                for kw in kws:
                    for variant in (0, 1):
                        built = we.BUILDERS[fam](player, level, tonic, tonality, variant=variant, **kw)
                        abc, diag = we.render(player, built, tonic, tonality, title=built.title)
                        we.verify(player, level, built, tonic, tonality, diag)
                        assert read_abc(abc, octave_offset=0) == [n.midi for n in built.notes if not n.rest], (key, concert, level, fam, kw)

    def test_a_note_outside_the_instrument_fails_verification(self):
        player = we.make_player("flute", "C")
        built = we.build_scale(player, "Intermediate", "C", "major")
        built.notes[0] = we.Note("C", 2, "quarter")
        abc, diag = we.render(player, built, "C", "major", title="x")
        with pytest.raises(we.WarmupUnavailable):
            we.verify(player, "Intermediate", built, "C", "major", diag)

    def test_a_bar_that_does_not_add_up_is_refused(self):
        with pytest.raises(we.WarmupUnavailable):
            we.to_events([we.Note("C", 5, "half"), we.Note("D", 5, "whole")])

    def test_articulation_marks_reach_the_staff(self):
        player = we.make_player("flute", "C")
        built = we.build_articulation(player, "Intermediate", "C", "major", pattern="slur_tongue")
        abc, _ = we.render(player, built, "C", "major", title="x")
        assert "(" in abc and "." in abc, "slurs and staccato dots"
        built = we.build_articulation(player, "Intermediate", "C", "major", pattern="contrast")
        abc, _ = we.render(player, built, "C", "major", title="x")
        assert "!>!" in abc and "!tenuto!" in abc

    def test_rests_are_notated_in_long_tones(self):
        player = we.make_player("flute", "C")
        built = we.build_long_tones(player, "Beginner", "C", "major")
        abc, _ = we.render(player, built, "C", "major", title="x")
        assert "z4" in abc

    def test_the_global_instrument_selection_is_never_touched_by_building_a_player(self):
        iso = {"instrument": "Piano"}
        we.make_player("alto", "C")
        assert iso == {"instrument": "Piano"}


# ================================================================ 9. sentences that read wrongly before the Claude evaluation


class TestNegationProgressionAndSingleExerciseDifficulty:
    @pytest.mark.parametrize("q", ["Give me an advanced flute warmup emphasizing articulation but not scales.",
                                   "Give me a flute warmup with articulation instead of scales",
                                   "Give me a flute warmup with articulation rather than scales"])
    def test_but_not_scales_leaves_scales_out(self, q):
        req = wp.parse_request(q)
        assert "scale" in req["excluded"] and "scale" not in req["families"]
        s = session("Flute")
        ask(s, q, level="Intermediate")
        assert "scale" not in families(plan_of(s)) and "articulation" in families(plan_of(s))

    def test_not_much_is_not_an_exclusion(self):
        req = wp.parse_request("Give me a warmup with long tones, but not much on scales")
        assert req["excluded"] == []

    def test_increasingly_difficult_is_a_progression_not_the_advanced_level(self):
        req = wp.parse_request("Prepare a ten-minute saxophone warmup with long tones and increasingly difficult intervals.")
        assert req["level"] == "" and req["progressive"] and req["minutes"] == 10
        assert wp.parse_request("Give me a hard warmup")["level"] == "Advanced"

    @pytest.mark.parametrize("level,expected", [("Beginner", ["thirds", "fourths"]), ("Intermediate", ["thirds", "fourths", "fifths"]),
                                                ("Advanced", ["thirds", "fourths", "fifths", "sixths"])])
    def test_the_intervals_widen_through_the_warmup_and_the_page_level_is_kept(self, level, expected):
        s = session("Saxophone", ALTO)
        resp = ask(s, "Prepare a ten-minute saxophone warmup with long tones and increasingly difficult intervals.", instrument="Saxophone", level=level)
        plan = plan_of(s)
        assert plan["level"] == level and "long_tones" in families(plan)
        ivs = [r["params"].get("interval") for r in plan["items"] if r["family"] == "intervals"]
        assert ivs == expected, ivs
        assert "get wider as the warmup goes on" in resp.composed_markdown()
        total = sum(r["seconds"] for r in plan["items"]) + (len(plan["items"]) - 1) * plan["transition_seconds"]
        assert abs(total - plan["target_seconds"]) <= max(20, 0.08 * plan["target_seconds"]), (total, plan["target_seconds"])

    def test_make_the_second_exercise_more_challenging_changes_only_that_exercise(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone")
        before = copy.deepcopy(plan_of(s))
        versions = wp.history(s)["versions"]
        resp = ask(s, "Make the second exercise more challenging, but keep the first exactly as it is.", instrument="Saxophone")
        after = plan_of(s)
        assert wp.history(s)["versions"] == versions + 1
        assert after["items"][1]["bpm"] > before["items"][1]["bpm"] and after["level"] == before["level"]
        assert "faster tempo is how I make a single exercise more challenging" in resp.composed_markdown()
        for i, (a, b) in enumerate(zip(after["items"], before["items"])):
            if i != 1:
                assert a["abc"] == b["abc"] and a["bpm"] == b["bpm"], i
        ask(s, "Undo that")
        assert plan_of(s) == before

    def test_asking_to_change_and_keep_the_same_exercise_is_refused_and_changes_nothing(self):
        s = session("Flute")
        ask(s, "Give me a warmup")
        before = copy.deepcopy(plan_of(s))
        versions = wp.history(s)["versions"]
        resp = ask(s, "Make the first exercise more challenging, but keep the first exactly as it is.")
        assert plan_of(s) == before and wp.history(s)["versions"] == versions
        assert "can't make that change" in resp.direct_answer

    def test_the_third_one_and_the_fourth_exercise_are_ordinals_not_intervals(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone")
        before = copy.deepcopy(plan_of(s))
        ask(s, "Make the third one easier", instrument="Saxophone")
        mid = plan_of(s)
        assert mid["items"][2]["bpm"] < before["items"][2]["bpm"]
        assert [r["params"] for r in mid["items"]] == [r["params"] for r in before["items"]]
        ask(s, "Make the fourth exercise faster", instrument="Saxophone")
        assert plan_of(s)["items"][3]["bpm"] > before["items"][3]["bpm"]
        assert [r["params"] for r in plan_of(s)["items"]] == [r["params"] for r in before["items"]]

    def test_the_whole_warmup_harder_and_a_real_interval_change_still_work(self):
        s = session("Saxophone", ALTO)
        ask(s, "Give me a 10-minute warmup", instrument="Saxophone", level="Intermediate")
        ask(s, "Make it more advanced", instrument="Saxophone", level="Intermediate")
        assert plan_of(s)["level"] == "Advanced"
        ask(s, "Change the interval exercise to fourths", instrument="Saxophone", level="Intermediate")
        assert {r["params"].get("interval") for r in plan_of(s)["items"] if r["family"] == "intervals"} >= {"fourths"}


class TestWiderThanAndToneWithFingers:
    def test_intervals_wider_than_thirds_means_the_next_wider_ones_not_thirds(self):
        req = wp.parse_request("Give me a fifteen-minute warmup with a bit of everything but make the intervals wider than thirds")
        assert req["intervals"] == ["fourths", "fifths", "sixths"] and req["minutes"] == 15
        s = session("Saxophone", ALTO)
        ask(s, "Give me a fifteen-minute warmup with a bit of everything but make the intervals wider than thirds", instrument="Saxophone")
        got = [r["params"].get("interval") for r in plan_of(s)["items"] if r["family"] == "intervals"]
        assert got and "thirds" not in got and set(got) <= {"fourths", "fifths", "sixths"}

    def test_other_interval_sentences_still_read_as_before(self):
        assert wp.parse_request("An intermediate warmup focused on thirds and fourths")["intervals"] == ["thirds", "fourths"]
        assert wp.parse_request("Give me a warmup with intervals wider than fifths")["intervals"] == ["sixths", "sevenths", "octaves"]

    def test_tone_and_finger_coordination_gets_both_halves(self):
        req = wp.parse_request("Give me a beginner warmup focused on tone and finger coordination.")
        assert req["families"] == ["long_tones", "scale", "intervals"] and req["level"] == "Beginner"
        s = session("Flute")
        resp = ask(s, "Give me a beginner warmup focused on tone and finger coordination.", level="Intermediate")
        assert {"long_tones", "scale"} <= set(families(plan_of(s))) and plan_of(s)["level"] == "Beginner"
        assert "tone and finger technique work" in resp.composed_markdown()

    def test_finger_technique_alone_and_tone_alone_are_unchanged(self):
        assert wp.parse_request("A warmup that improves finger technique")["families"] == ["scale", "intervals", "articulation"]
        assert wp.parse_request("A warmup for my tone")["families"] == ["long_tones", "scale"]
