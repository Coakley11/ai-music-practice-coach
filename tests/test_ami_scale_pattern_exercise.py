"""AMI M1d: scale patterns (AMI's own generator) become structured exercises the conversation can keep revising."""

from __future__ import annotations

import re

import pytest

from music_coach_ami import conversation_state as cs
from music_coach_ami import exercise_scale_pattern as sp
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_followup import last_exercise
from music_coach_ami.pipeline import run_coach_submit

SECTION = {"A": ["Cm7", "Fm7", "Dm7b5", "G7"]}
ASK = "Give me an advanced scale pattern over Blue Bossa."
_Q = re.compile(r"^Q:\S+=(\d+)", re.M)


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    monkeypatch.setattr(AnthropicTransport, "complete", lambda self, **kw: (_ for _ in ()).throw(AssertionError("LIVE API CALL")))


def ctx(instrument="Flute", level="Advanced", song="Blue Bossa"):
    return {"instrument": instrument, "level": level, "focus": "Improvisation", "active_song": {"title": song, "key": "Cm", "default_key": "Cm"},
            "chart_sections": {k: list(v) for k, v in SECTION.items()}, "chart_sections_key": "Cm", "bpm": 96, "practice_key_hint": "Cm"}


def session(instrument="Flute"):
    return {"_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel", "instrument": instrument, "practice_key": "Cm", "backing_bpm": 112}


def ask(s, q, instrument="Flute", **kw):
    return run_coach_submit(q, s, ami_ctx=ctx(instrument, **kw))[1]


def tempo(resp):
    m = _Q.search(resp.notation_abc or "")
    return int(m.group(1)) if m else 0


def start(s=None, instrument="Flute", q=ASK):
    s = s if s is not None else session(instrument)
    resp = ask(s, q, instrument)
    assert resp.diagnostics.get("generated_exercise_id"), resp.diagnostics.get("scale_pattern_exercise_failed")
    return s, resp


# ---- conversion ----------------------------------------------------------------------------------------------------
def test_the_blue_bossa_request_now_creates_a_structured_exercise():
    s, resp = start()
    ex = resp.diagnostics["generated_exercise"]
    assert ex["engine"] == sp.ENGINE and ex["vocabulary"] == "degree_pattern"
    assert len(ex["notes"]) == len(ex["midi"]) == 32 and ex["bars"] == 4 and ex["meter"] == "4/4"
    assert ex["context"]["song_title"] == "Blue Bossa" and ex["context"]["section"] == "A" and ex["context"]["tempo_bpm"] == 96
    assert ex["tempo_bpm"] == 96 and resp.diagnostics["last_exercise_stored"] is True and ex["validation"]["ok"]
    assert last_exercise(s).id == ex["id"] and cs.current_version(s) is not None


def test_conversion_does_not_change_the_answer_the_player_gets(monkeypatch):
    s1, with_adapter = start()
    monkeypatch.setattr(sp, "build_exercise", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("adapter off")))
    without = ask(session(), ASK)
    assert "scale_pattern_exercise_failed" in without.diagnostics and not without.diagnostics.get("generated_exercise_id")
    for field in ("direct_answer", "practice_steps", "what_to_listen_for", "suggested_next_action", "notation_abc", "notation_abc_sections"):
        assert getattr(with_adapter, field) == getattr(without, field), field


@pytest.mark.parametrize("instrument", ["Flute", "Alto Saxophone", "Tenor Saxophone", "Soprano Saxophone", "Baritone Saxophone", "Bb Trumpet", "Bb Clarinet", "Violin", "Voice"])
@pytest.mark.parametrize("question", [ASK, "Give me a beginner scale pattern", "Give me a 2-bar scale pattern in thirds", "Give me an 8-bar Dorian scale pattern"])
def test_rerendering_the_stored_exercise_reproduces_the_original_notation_exactly(instrument, question):
    s, resp = start(instrument=instrument, q=question)
    ex = last_exercise(s)
    abc, _ = sp.render(ex, bpm=tempo(resp))
    assert abc == resp.notation_abc and ex.validation["ok"]


@pytest.mark.parametrize("instrument, shift", [("Flute", 0), ("Alto Saxophone", 9), ("Tenor Saxophone", 2), ("Soprano Saxophone", 2),
                                               ("Baritone Saxophone", 9), ("Bb Trumpet", 2), ("Bb Clarinet", 2)])
def test_written_pitch_is_the_correct_transposition_of_the_concert_pitch(instrument, shift):
    _s, resp = start(instrument=instrument)
    ex = resp.diagnostics["generated_exercise"]
    assert ex["midi"][0] % 12 == 0 and ex["tonic"] == "C"                       # concert C major
    assert {(w - c) % 12 for c, w in zip(ex["midi"], ex["written"]["midi"])} == {shift}
    assert len(ex["written"]["notes"]) == len(ex["notes"])
    assert ex["context"]["written_transposition_applied"] == bool(shift)


def test_concert_midi_matches_the_notes_and_the_scale():
    _s, resp = start()
    ex = resp.diagnostics["generated_exercise"]
    pcs = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    assert [m % 12 for m in ex["midi"]] == [pcs[n[0]] for n in ex["notes"]]
    assert {n for n in ex["notes"]} <= set(ex["collection_notes"]) and ex["chord"] == "" and ex["chords"] == []
    assert "no chord" in ex["provenance"]["harmony"]


def test_durations_fill_the_bars_and_each_note_has_one_event():
    _s, resp = start()
    ex = resp.diagnostics["generated_exercise"]
    sounding = [e for e in ex["rhythm_events"] if not e["rest"]]
    assert [e["n"] for e in sounding] == list(range(len(ex["notes"])))
    from fractions import Fraction

    assert sum(Fraction(e["dur"]) for e in ex["rhythm_events"]) == 16


def test_practice_key_ownership_the_app_value_is_stored_and_nothing_is_written_back():
    s, resp = start()
    before = {k: v for k, v in s.items() if not k.startswith("_ami_")}
    ex = resp.diagnostics["generated_exercise"]
    assert ex["context"]["concert_key"] in ("C", "Cm") and ex["context"]["key_candidates"]["scale_tonic"] == "C"
    for q in ("Make it slower", "Make it harder", "Add accents", "Undo that"):
        ask(s, q)
    assert {k: v for k, v in s.items() if not k.startswith("_ami_") and not k.startswith("_music_")} == {k: v for k, v in before.items() if not k.startswith("_music_")}


def test_an_adapter_failure_leaves_the_legacy_answer_and_no_stale_exercise(monkeypatch):
    s, first = start()
    monkeypatch.setattr(sp, "build_exercise", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    resp = ask(s, "Give me a beginner scale pattern")
    assert resp.notation_abc and "scale_pattern_exercise_failed" in resp.diagnostics
    assert AMI_LAST_EXERCISE_KEY not in s          # the earlier exercise was cleared when a newer unstructured answer replaced it
    assert "no exercise from this conversation" in ask(s, "Make it slower").direct_answer.lower()


def test_an_exercise_the_engine_itself_flags_is_not_structured():
    s = session("Piano")
    resp = ask(s, ASK, "Piano")
    assert resp.notation_abc and not resp.diagnostics.get("generated_exercise_id")
    assert "validation failed" in resp.diagnostics.get("scale_pattern_exercise_failed", "")


# ---- the Blue Bossa conversation -------------------------------------------------------------------------------------
def test_blue_bossa_conversation_keeps_one_exercise_through_every_step():
    s, first = start()
    base = first.diagnostics["generated_exercise"]
    slower = ask(s, "Make it slower")
    assert tempo(slower) == 86 and slower.diagnostics["generated_exercise"]["notes"] == base["notes"]
    assert slower.diagnostics["generated_exercise"]["rhythm_events"] == base["rhythm_events"]
    assert _Q.sub("Q:X", slower.notation_abc) == _Q.sub("Q:X", first.notation_abc)
    harder = ask(s, "Make it harder")
    assert harder.diagnostics["followup_kind"] == "harder" and tempo(harder) == 86 and harder.diagnostics["scale_pattern_exercise"] is True
    h = harder.diagnostics["generated_exercise"]
    assert h["engine"] == sp.ENGINE and h["context"]["song_title"] == "Blue Bossa" and h["tonic"] == base["tonic"] and h["mode"] == base["mode"]
    assert h["transform"]["level_from"] == "Advanced" and h["transform"]["level_to"] == "Advanced+" and h["validation"]["ok"]
    assert h["notes"] != base["notes"] or h["rhythm_events"] != base["rhythm_events"]
    accents = ask(s, "Add accents")
    a = accents.diagnostics["generated_exercise"]
    assert a["notes"] == h["notes"] and a["midi"] == h["midi"] and a["rhythm_events"] == h["rhythm_events"] and any(a["accents"]) and not all(a["accents"])
    assert "!>!" in accents.notation_abc and tempo(accents) == 86
    assert "accented the downbeats" in accents.direct_answer
    undone = ask(s, "Undo that")
    assert undone.diagnostics["generated_exercise"] == harder.diagnostics["generated_exercise"] | {"tempo_bpm": 86} or \
        undone.diagnostics["generated_exercise"]["notes"] == h["notes"]
    assert undone.notation_abc == harder.notation_abc and "!>!" not in undone.notation_abc
    redone = ask(s, "Redo")
    assert redone.notation_abc == accents.notation_abc


def test_undo_returns_the_exact_original_scale_pattern():
    s, first = start()
    ask(s, "Make it slower")
    ask(s, "Make it harder")
    ask(s, "Add accents")
    for _ in range(3):
        last = ask(s, "Undo that")
    assert last.notation_abc == first.notation_abc and last.diagnostics["generated_exercise"] == first.diagnostics["generated_exercise"]


def test_the_ladder_goes_both_ways_and_stops_at_both_ends():
    s, _ = start()
    for want in ("Advanced+", "Advanced++"):
        assert ask(s, "Make it harder").diagnostics["generated_exercise"]["transform"]["level_to"] == want
    top = ask(s, "Make it harder")
    assert "already the hardest" in top.direct_answer and top.diagnostics["exercise_followup_failed"]
    for want in ("Advanced+", "Advanced", "Intermediate", "Beginner"):
        assert ask(s, "Make it easier").diagnostics["generated_exercise"]["transform"]["level_to"] == want
    assert "already the easiest" in ask(s, "Make it easier").direct_answer


def test_every_rung_is_a_valid_scale_pattern_in_every_supported_transposition():
    for instrument in ("Flute", "Alto Saxophone", "Tenor Saxophone", "Bb Trumpet"):
        s, _ = start(instrument=instrument)
        for _ in range(2):                       # Advanced -> Advanced+ -> Advanced++
            resp = ask(s, "Make it harder", instrument)
            ex = last_exercise(s)
            assert ex.validation["ok"], (instrument, ex.validation)
            abc, _c = sp.render(ex, bpm=tempo(resp))
            assert abc == resp.notation_abc


def test_difficulty_changes_keep_key_scale_song_and_tempo():
    s, first = start()
    ask(s, "Set it to 72 BPM")
    for q in ("Make it harder", "Make it easier", "Make it easier"):
        r = ask(s, q)
        ex = r.diagnostics["generated_exercise"]
        assert (ex["tonic"], ex["mode"], ex["context"]["song_title"], ex["context"]["concert_key"]) == ("C", "major", "Blue Bossa", first.diagnostics["generated_exercise"]["context"]["concert_key"])
        assert tempo(r) == 72 and ex["tempo_bpm"] == 72


def test_accents_with_a_named_target_and_unsupported_targets():
    s, first = start()
    r = ask(s, "Accent every second note")
    assert r.diagnostics.get("followup_kind") == "expression" and not r.diagnostics.get("exercise_followup_failed")
    assert sum(r.diagnostics["generated_exercise"]["accents"]) == len(first.diagnostics["generated_exercise"]["notes"]) // 2
    t = ask(s, "Add accents to the guide tones")
    assert t.diagnostics["exercise_followup_failed"] and "chord roles" in t.direct_answer and "unchanged" in t.direct_answer
    d = ask(s, "Add a crescendo")
    assert d.diagnostics["exercise_followup_failed"] and "Dynamics" in d.direct_answer


@pytest.mark.parametrize("q", ["Give me another one", "Move it up a step", "Keep the notes but change the rhythm", "Keep the rhythm but change the notes",
                               "Add some chromatic approaches", "Change the pattern to fourths"])
def test_unsupported_followups_get_a_clear_answer_and_leave_the_exercise_alone(q):
    s, first = start()
    before = dict(s[AMI_LAST_EXERCISE_KEY])
    r = ask(s, q)
    assert "unchanged" in r.direct_answer and r.diagnostics.get("exercise_followup_failed") or r.diagnostics.get("exercise_revision_failed")
    assert s[AMI_LAST_EXERCISE_KEY] == before and cs.history(s)["versions"] == 1


# ---- stale context ---------------------------------------------------------------------------------------------------
def test_a_song_change_cannot_reuse_the_exercise():
    s, _ = start()
    for q in ("Make it slower", "Make it harder", "Undo that"):
        r = run_coach_submit(q, s, ami_ctx=ctx(song="Autumn Leaves"))[1]
        assert "built for **Blue Bossa**" in r.direct_answer and "**Autumn Leaves**" in r.direct_answer
        assert r.diagnostics["exercise_revision_failure_reason"] == "song_changed"
    assert cs.history(s)["versions"] == 1 and cs.working_tempo(s) == 96
    back = run_coach_submit("Make it slower", s, ami_ctx=ctx())[1]
    assert tempo(back) == 86


def test_a_new_request_on_the_new_song_is_not_blocked():
    s, _ = start()
    r = run_coach_submit(ASK, s, ami_ctx=ctx(song="Autumn Leaves"))[1]
    assert r.diagnostics.get("generated_exercise_id") and r.diagnostics["generated_exercise"]["context"]["song_title"] == "Autumn Leaves"


def test_account_and_workspace_isolation_for_scale_pattern_exercises():
    s, _ = start()
    s["_suite_auth_user_id"] = "u2"
    assert "no exercise from this conversation" in ask(s, "Make it slower").direct_answer.lower()
    s2, _ = start()
    s2["_suite_active_workspace_id"] = "ariel"
    assert "no exercise from this conversation" in ask(s2, "Undo that").direct_answer.lower()


def test_no_billable_call_is_made_by_any_scale_pattern_revision():
    s, _ = start()
    for q in ("Make it slower", "Make it harder", "Add accents", "Undo that", "Redo", "Make it easier"):
        ask(s, q)   # the autouse fixture raises on any live API call


def test_six_eight_tempo_marking_is_swapped_correctly():
    from music_coach_ami import exercise_revision as er

    assert er._swap_tempo("X:1\nQ:3/8=96\nK:C", 80) == "X:1\nQ:3/8=80\nK:C"
    assert cs.tempo_of_abc("X:1\nQ:3/8=96\nK:C") == 96


def test_the_list_of_what_can_change_is_specific_to_scale_patterns():
    s, _ = start()
    msg = " ".join(ask(s, "Change the pattern to fourths").practice_steps)
    assert "harder or easier" in msg and "accents" in msg and "moving or sequencing" not in msg and "new notes" not in msg
