"""Musician acceptance examples with independent MIDI/ABC expectations."""
import copy
import logging

import pytest

from music_coach_ami.pipeline import run_coach_submit
from music_coach_ami import warmup_plan as wp
from music_coach_ami.claude_client import AnthropicTransport
from tests.test_abc_bar_accidentals import read_abc
from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY


@pytest.fixture(autouse=True)
def no_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda *a, **k: pytest.fail("API call"))
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(previous)


def session():
    return {"instrument": "Flute", "_suite_auth_user_id": "a", "_suite_active_workspace_id": "one"}


def ask(s, q, level="Beginner", instrument="Flute", focus="Tone"):
    return run_coach_submit(q, s, ami_ctx={"instrument": instrument, "level": level,
                                         "display_key": "C", "focus": focus})[1]


def row(s):
    p = wp.current(s)
    assert len(p["items"]) == 1
    assert p["spec"]["single"]
    return p["items"][0]


def test_beginner_scale_direction_exact_undo_redo_explanation():
    s = session()
    r = ask(s, "Give me a slow ascending A major scale.")
    assert not r.diagnostics["single_exercise_failed"]
    expected = [69, 71, 73, 74, 76, 78, 80, 81]
    assert row(s)["written_midi"] == expected
    assert row(s)["bpm"] == 50
    original = copy.deepcopy(wp.current(s))
    ask(s, "Now make it descending.")
    assert row(s)["written_midi"] == expected[::-1]
    descending = copy.deepcopy(wp.current(s))
    hist = wp.history(s)
    explain = ask(s, "Explain why these notes work.")
    assert "A5" in explain.direct_answer and "C#5" in explain.direct_answer
    assert wp.current(s) == descending and wp.history(s) == hist
    ask(s, "Undo.")
    assert wp.current(s) == original
    ask(s, "Redo.")
    assert wp.current(s) == descending


def test_three_comfortable_long_tones_are_exactly_three():
    s = session()
    ask(s, "Give me three long tones.")
    assert len(row(s)["written_midi"]) == 3
    assert all(67 <= m <= 76 for m in row(s)["written_midi"])
    assert row(s)["durations"].count("whole") == 6  # three tones, three breath rests


@pytest.mark.parametrize("register,limits", [("low", (60, 72)), ("high", (84, 96)), ("middle", (69, 87))])
def test_actual_flute_register(register, limits):
    s = session()
    r = ask(s, f"Give me an advanced {register}-register flute exercise.")
    assert not r.diagnostics["single_exercise_failed"]
    assert min(row(s)["written_midi"]) >= limits[0]
    assert max(row(s)["written_midi"]) <= limits[1]


def test_abmaj7_buster_and_tenor_exact_octave_transposition_sidebar_unchanged():
    s = session()
    s.update(instrument="Saxophone", **{SAX_KEY: "Alto saxophone (Eb)"})
    settings = {k: s[k] for k in ("instrument", SAX_KEY)}
    r = ask(s, "Give me an advanced alto sax A-flat major seventh arpeggio finger-buster.")
    assert not r.diagnostics["single_exercise_failed"]
    a = copy.deepcopy(row(s))
    assert {m % 12 for m in a["sounding_midi"]} == {8, 0, 3, 7}
    assert {m % 12 for m in a["written_midi"]} == {5, 9, 0, 4}
    assert all(w - c == 9 for w, c in zip(a["written_midi"], a["sounding_midi"]))
    assert "sixteenth" in a["durations"]
    assert max(abs(b-a) for a,b in zip(a["written_midi"], a["written_midi"][1:])) >= 12
    ask(s, "Change it to tenor saxophone.")
    t = row(s)
    assert {m % 12 for m in t["sounding_midi"]} == {8, 0, 3, 7}
    assert all(w - c == 14 for w, c in zip(t["written_midi"], t["sounding_midi"]))
    assert {k: s[k] for k in settings} == settings


@pytest.mark.parametrize("quality,pcs", [("major seventh", {8,0,3,7}), ("dominant seventh", {8,0,3,6}), ("major", {8,0,3})])
def test_chord_qualities_are_different(quality, pcs):
    s = session()
    r = ask(s, f"Give me an A-flat {quality} arpeggio.")
    assert not r.diagnostics["single_exercise_failed"]
    assert {m % 12 for m in row(s)["sounding_midi"]} == pcs


@pytest.mark.parametrize("q", ["Give me a bass guitar E minor warmup."])
def test_unsupported_techniques_are_truthful(q):
    s = session()
    r = ask(s, q)
    assert r and not r.notation_abc
    assert wp.current(s) is None
    assert "can't" in r.direct_answer or "verified" in r.direct_answer


@pytest.mark.parametrize("field,value", [("_suite_auth_user_id", "b"), ("_suite_active_workspace_id", "two")])
def test_owner_isolation(field, value):
    s = session()
    ask(s, "Give me an A major scale.")
    s[field] = value
    ask(s, "Explain why these notes work.")
    assert wp.current(s) is None


def test_rhythm_only_and_tempo_preserve_notes():
    s = session()
    ask(s, "Give me an A major scale.")
    old = row(s)["written_midi"][:]
    ask(s, "Keep the notes but make the rhythm harder.")
    assert row(s)["written_midi"] == old and "sixteenth" in row(s)["durations"]
    ask(s, "Make it faster.")
    assert row(s)["written_midi"] == old and row(s)["bpm"] == 82


def test_explicit_request_over_focus_and_new_full_warmup():
    s = session()
    ask(s, "Give me an A major scale.", focus="Articulation")
    assert row(s)["family"] == "scale"
    r = ask(s, "Give me a ten-minute warmup.")
    assert r.diagnostics["warmup"] and not wp.current(s)["spec"].get("single")


def test_ambiguous_sax_requests_clarification():
    s = session()
    r = ask(s, "Give me a saxophone A major scale.")
    assert not r.notation_abc and "Which saxophone" in r.direct_answer


def test_abc_matches_independent_stored_pitch_reader():
    s = session()
    ask(s, "Give me an A major scale.")
    # read_abc has an independent tokenizer and octave interpretation.
    parsed = read_abc(row(s)["abc"])
    assert parsed == row(s)["written_midi"]


@pytest.mark.parametrize("who,offset", [("flute",0),("piano",0),("soprano",2),("alto",9),("tenor",14),("baritone",21),("clarinet",2),("trumpet",2)])
def test_all_existing_profiles_independent_offsets_and_staff(who, offset):
    from music_coach_ami import flexible_single as fs, warmup_engine as we
    spec = {"instrument":who,"concert_key":"D" if who in ("soprano", "tenor") else "C","family":"scale","quality":"major","level":"Intermediate",
            "register":"middle","direction":"ascending","buster":False,"count":3,"reps":1,"bpm":72,"rhythm":"","articulation":"","single":True}
    p = fs.build(spec)
    r = p["items"][0]
    assert p["player"]["offset"] == offset
    assert all(w-c == offset for w,c in zip(r["written_midi"],r["sounding_midi"]))
    assert read_abc(r["abc"]) == r["written_midi"]
    assert {m%12 for m in r["sounding_midi"]} <= ({1,2,4,6,7,9,11} if who in ("soprano", "tenor") else {0,2,4,5,7,9,11})


def test_new_exercise_identity_changes_deduplication_signature():
    from music_coach_ami.exercise_context import exercise_authority_signature
    s = session()
    ask(s, "Give me an A major scale.")
    a = exercise_authority_signature(s, "Explain why these notes work.")
    ask(s, "Give me a G major scale.")
    b = exercise_authority_signature(s, "Explain why these notes work.")
    assert a != b


@pytest.mark.parametrize("focus,family", [("Tone","long_tones"),("Articulation","articulation"),("Technique","intervals"),("Melody","scale")])
def test_full_warmup_uses_real_focus(focus, family):
    s = session()
    ask(s, "Give me a ten-minute warmup.", focus=focus)
    p = wp.current(s)
    assert p["spec"]["focus"] == focus.lower()
    assert family in p["spec"]["families"]
    weights = wp._weights(p["spec"])
    assert weights[family] > wp.BASE_WEIGHT[family]


def test_harmony_focus_uses_active_chart_and_missing_chart_is_truthful():
    from tests.song_fixtures import song_session
    s = song_session("Blue Bossa")
    r = run_coach_submit("Give me a warmup.", s, ami_ctx={"instrument":"Saxophone","level":"Intermediate","display_key":"Cm","focus":"Harmony"})[1]
    p = wp.current(s)
    assert p and p["spec"]["song"]["title"] == "Blue Bossa"
    assert {r["family"] for r in p["items"]} == {"guide_tones", "chord_tones"}
    other = session()
    response = ask(other, "Give me a warmup.", focus="Harmony")
    assert not response.notation_abc and "chart" in response.direct_answer


def test_explicit_scale_beats_harmony_focus():
    s = session()
    r = ask(s, "Give me an A major scale.", focus="Harmony")
    assert row(s)["written_midi"] == [69,71,73,74,76,78,80,81]


def test_compound_direction_and_tempo_revision():
    s = session()
    ask(s,"Give me an A major scale.")
    before = row(s)["written_midi"][:]
    ask(s,"Make it descending at 60 bpm.")
    assert row(s)["written_midi"] == before[::-1] and row(s)["bpm"] == 60


def test_exact_user_beginner_scale_and_revision():
    s = session()
    r = ask(s, "Give me a slow ascending A major scale for flute.")
    assert r.source_solver == "InstrumentExercise"
    assert row(s)["written_midi"] == [69,71,73,74,76,78,80,81]
    before = row(s)["written_midi"][:]
    ask(s,"Now make it descending.")
    assert row(s)["written_midi"] == before[::-1]


def test_exact_user_difficult_major_seventh_buster():
    s = session()
    r = ask(s,"Give me a difficult A-flat major seventh finger-buster for alto sax.")
    assert not r.diagnostics["single_exercise_failed"]
    assert wp.current(s)["level"] == "Advanced"
    assert {m%12 for m in row(s)["sounding_midi"]} == {8,0,3,7}
    assert "sixteenth" in row(s)["durations"]
    assert max(abs(b-a) for a,b in zip(row(s)["written_midi"],row(s)["written_midi"][1:])) >= 12


def test_generic_tenor_exercise_override_is_accessible_and_does_not_change_sidebar():
    s = session()
    s.update(instrument="Saxophone", **{SAX_KEY:"Alto saxophone (Eb)"})
    original = {"instrument":s["instrument"], SAX_KEY:s[SAX_KEY]}
    r = ask(s,"Give me a tenor saxophone exercise.",instrument="Saxophone",level="Intermediate")
    assert not r.diagnostics["single_exercise_failed"]
    assert wp.current(s)["player"]["key"] == "tenor"
    assert all(w-c==14 for w,c in zip(row(s)["written_midi"],row(s)["sounding_midi"]))
    assert {k:s[k] for k in original} == original


def test_generic_high_flute_plural_and_lower_revision():
    s = session()
    r = ask(s,"Give me high-register flute exercises.",level="Advanced")
    assert not r.diagnostics["single_exercise_failed"]
    before = copy.deepcopy(row(s))
    assert min(before["written_midi"]) >= 84
    ask(s,"Make them lower.",level="Advanced")
    assert max(row(s)["written_midi"]) <= 72
    assert max(row(s)["written_midi"]) < min(before["written_midi"])
    assert read_abc(row(s)["abc"]) == row(s)["written_midi"]


def test_exact_song_arpeggio_reuses_slice2b_for_one_chart_pass():
    from tests.song_fixtures import song_session
    from tests import song_oracle as oracle
    from music_coach_ami import warmup_song as ws
    s = song_session("Blue Bossa",level="Intermediate")
    r = run_coach_submit("Give me a difficult arpeggio exercise over Blue Bossa.",s,
        ami_ctx={"instrument":"Saxophone","level":"Intermediate","focus":"Tone","display_key":"Cm"})[1]
    p = wp.current(s)
    assert p and p["spec"]["single_song"] and p["level"]=="Advanced"
    assert len(p["items"])==1 and p["items"][0]["reps"]==1
    assert p["items"][0]["family"]=="chord_tones"
    assert "10-minute" not in r.direct_answer and "one chart pass" in r.direct_answer
    assert not any("Between exercises" in step for step in r.practice_steps)
    assert "make it shorter" not in r.suggested_next_action
    song=p["spec"]["song"];section=p["spec"]["song_sel"]["section"]
    assert song["title"]=="Blue Bossa"
    assert oracle.check_chordline(p["items"][0]["abc"],ws.section_slots(song,section),9,approach=False)==[]
    before=copy.deepcopy(p); history=wp.history(s)
    explain=run_coach_submit("Explain why these notes work.",s,ami_ctx={"instrument":"Saxophone","level":"Intermediate","display_key":"Cm"})[1]
    assert "Why these notes work" in explain.direct_answer
    assert wp.current(s)==before and wp.history(s)==history


def test_song_warm_me_up_replaces_standalone_before_read_only_explain():
    from tests.song_fixtures import song_session
    s = song_session("Blue Bossa", level="Intermediate")
    ctx = {"instrument":"Saxophone","level":"Intermediate","display_key":"Cm","focus":"Tone"}
    run_coach_submit("Give me high-register flute exercises.",s,ami_ctx={**ctx,"level":"Advanced"})
    assert wp.current(s)["spec"]["single"]
    response = run_coach_submit("Warm me up for soloing over Blue Bossa.",s,ami_ctx=ctx)[1]
    plan = copy.deepcopy(wp.current(s)); history = wp.history(s)
    assert response and not plan["spec"].get("single")
    assert plan["player"]["key"]=="alto" and plan["level"]=="Intermediate"
    assert {"chord_tones","approach_notes"} <= {r["family"] for r in plan["items"]}
    why = run_coach_submit("Explain why these notes work.",s,ami_ctx=ctx)[1]
    assert "Each approach and what it resolves to" in why.direct_answer
    assert wp.current(s)==plan and wp.history(s)==history


def test_single_song_duration_refusal_and_tempo_preserve_one_pass():
    from tests.song_fixtures import song_session
    s=song_session("Blue Bossa",level="Intermediate")
    ctx={"instrument":"Saxophone","level":"Intermediate","display_key":"Cm"}
    run_coach_submit("Give me a difficult arpeggio exercise over Blue Bossa.",s,ami_ctx=ctx)
    before=copy.deepcopy(wp.current(s)); history=wp.history(s)
    r=run_coach_submit("Make it 5 minutes.",s,ami_ctx=ctx)[1]
    assert "one chart pass" in r.direct_answer
    assert wp.current(s)==before and wp.history(s)==history
    run_coach_submit("Make exercise 1 slower.",s,ami_ctx=ctx)
    after=wp.current(s)
    assert after["items"][0]["reps"]==1
    assert after["items"][0]["bpm"]<before["items"][0]["bpm"]
