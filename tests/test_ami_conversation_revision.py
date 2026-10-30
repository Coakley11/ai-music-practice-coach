"""AMI M1a: conversational memory, tempo revisions, undo / redo and the unsupported-revision guard."""

from __future__ import annotations

import re

import pytest

from music_coach_ami import conversation_state as cs
from music_coach_ami.claude_client import AnthropicTransport
from music_coach_ami.exercise_bridge import AMI_LAST_EXERCISE_KEY
from music_coach_ami.exercise_followup import last_exercise
from music_coach_ami.exercise_revision import parse_revision
from music_coach_ami.pipeline import run_coach_submit

CTX = {
    "instrument": "Flute", "level": "Intermediate", "focus": "Improvisation",
    "active_song": {"title": "Blue Bossa", "key": "Cm", "default_key": "Cm"},
    "chart_sections": {"A": ["Cm7", "Fm7", "Dm7b5", "G7"]}, "chart_sections_key": "Cm", "bpm": 96, "practice_key_hint": "Cm",
}
_Q = re.compile(r"^Q:1/4=(\d+)", re.M)


@pytest.fixture(autouse=True)
def _no_live_api(monkeypatch):
    def boom(self, **kw):
        raise AssertionError("LIVE API CALL in a deterministic revision test")

    monkeypatch.setattr(AnthropicTransport, "complete", boom)


@pytest.fixture
def session():
    return {"_suite_auth_user_id": "u1", "_suite_active_workspace_id": "daniel", "practice_key": "Cm", "backing_bpm": 112}


def ask(session, question, ctx=None):
    return run_coach_submit(question, session, ami_ctx=dict(ctx or CTX))[1]


def tempo(resp) -> int:
    m = _Q.search(resp.notation_abc)
    return int(m.group(1)) if m else 0


def strip_tempo(abc: str) -> str:
    return _Q.sub("Q:1/4=X", abc)


def start(session):
    resp = ask(session, "Give me a guide tone line over Cm7")
    assert resp.diagnostics.get("generated_exercise_id") and tempo(resp) == 96
    return resp


# ---- parsing ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q, mode", [
    ("Make it slower", "slower"), ("make it faster", "faster"), ("slower", "slower"), ("Slow it down", "slower"), ("speed it up", "faster"),
    ("Make it a bit slower", "slower"), ("Please make it much faster", "faster"), ("Slow it down by 10%", "slower"),
    ("Speed it up by 15 bpm", "faster"), ("Make it 20% faster", "faster"), ("Set it to 100 BPM", "set"), ("play it at 80 bpm", "set"),
    ("Set the tempo to 72", "set"), ("Return to the previous tempo", "previous"), ("go back to the last tempo", "previous"),
])
def test_tempo_phrases_are_recognised(q, mode):
    rev = parse_revision(q, has_exercise=True)
    assert rev is not None and rev.kind == "tempo" and rev.mode == mode


@pytest.mark.parametrize("q", [
    "How do I play faster?", "What tempo should I practice Blue Bossa at?", "Why do I rush when I speed up?", "slower tempos are harder",
    "Make it a great day", "Go back to the original", "How should I practice the verse?", "Explain the Dorian mode",
])
def test_ordinary_questions_are_left_alone(q):
    rev = parse_revision(q, has_exercise=True)
    assert rev is None or rev.kind == "unsupported" and rev.category == "other" and q == "Make it a great day"


@pytest.mark.parametrize("q", ["Undo that", "undo", "Undo the last change", "go back one step", "Redo", "redo that"])
def test_history_phrases_are_recognised(q):
    assert parse_revision(q, has_exercise=True).kind in ("undo", "redo")


def test_go_back_to_the_original_is_not_hijacked_from_the_existing_follow_up_engine():
    assert parse_revision("Go back to the original", has_exercise=True) is None


# ---- tempo ------------------------------------------------------------------------------------------------------
def test_tempo_change_touches_only_the_tempo(session):
    first = start(session)
    slower = ask(session, "Make it slower")
    assert tempo(slower) == 86
    assert strip_tempo(slower.notation_abc) == strip_tempo(first.notation_abc)        # every other notation byte identical
    a, b = first.diagnostics["generated_exercise"], slower.diagnostics["generated_exercise"]
    for field in ("notes", "midi", "rhythm_events", "rhythm_symbols", "articulation", "accents", "slur_groups", "dynamics", "chord", "chords",
                  "context", "written", "intent", "roles", "meter"):
        assert a[field] == b[field], field
    assert a["tempo_bpm"] == 96 and b["tempo_bpm"] == 86
    assert slower.diagnostics["notation_tempo"] == 86 and "86 BPM" in slower.direct_answer


def test_the_page_bpm_is_not_touched_by_a_tempo_revision(session):
    start(session)
    ask(session, "Set it to 100 BPM")
    assert session["backing_bpm"] == 112 and session["practice_key"] == "Cm"


def test_explicit_percentage_and_bpm_steps(session):
    start(session)
    assert tempo(ask(session, "Set it to 100 BPM")) == 100
    assert tempo(ask(session, "Slow it down by 10%")) == 90
    assert tempo(ask(session, "Speed it up by 15 bpm")) == 105
    assert tempo(ask(session, "a bit slower")) == 100


def test_return_to_the_previous_tempo(session):
    start(session)
    ask(session, "Set it to 100 BPM")
    ask(session, "Slow it down by 10%")
    assert tempo(ask(session, "Return to the previous tempo")) == 100


def test_return_to_previous_tempo_when_there_is_none_says_so_and_changes_nothing(session):
    start(session)
    resp = ask(session, "Return to the previous tempo")
    assert "no earlier tempo" in resp.direct_answer and cs.working_tempo(session) == 96 and cs.history(session)["versions"] == 1


@pytest.mark.parametrize("q", ["Set it to 500 BPM", "Set it to 20 BPM"])
def test_out_of_range_tempo_is_refused_without_changing_anything(session, q):
    start(session)
    resp = ask(session, q)
    assert "outside" in resp.direct_answer and cs.working_tempo(session) == 96 and cs.history(session)["versions"] == 1


def test_tempo_floor_and_ceiling_are_reported(session):
    start(session)
    ask(session, "Set it to 40 BPM")
    resp = ask(session, "make it slower")
    assert "slowest" in resp.direct_answer and cs.working_tempo(session) == 40


def test_followups_keep_the_working_tempo(session):
    start(session)
    ask(session, "Set it to 72 BPM")
    harder = ask(session, "Now make it harder")
    assert harder.diagnostics.get("followup_kind") == "harder" and tempo(harder) == 72
    accents = ask(session, "Add accents to the guide tones")
    assert tempo(accents) == 72
    assert cs.working_tempo(session) == 72


def test_tempo_in_the_missions_action_is_updated_when_the_action_carries_one(session):
    from music_coach_ami.exercise_revision import _retempo_action

    out, changed = _retempo_action({"kind": "single", "bpm": 96, "motif": {"notes": []}}, 80)
    assert changed and out["bpm"] == 80 and out["motif"] == {"notes": []}
    out, changed = _retempo_action({"kind": "span", "example": {"bpm": 96}}, 80)
    assert changed and out["example"]["bpm"] == 80
    out, changed = _retempo_action({"kind": "span", "example": {"x": 1}}, 80)
    assert not changed and out == {"kind": "span", "example": {"x": 1}}
    assert _retempo_action(None, 80) == (None, False)


def test_missions_is_only_claimed_when_it_actually_changed(session):
    start(session)
    resp = ask(session, "make it slower")
    assert ("Open in Missions will use" in resp.direct_answer) == bool(resp.diagnostics.get("missions_tempo_updated"))
    assert "play" not in resp.direct_answer.lower().replace("play it at", "") or "playback" not in resp.direct_answer.lower()


# ---- undo / redo ------------------------------------------------------------------------------------------------
def test_undo_restores_the_previous_exercise_exactly(session):
    first = start(session)
    ask(session, "Make it slower")
    undone = ask(session, "Undo that")
    assert undone.notation_abc == first.notation_abc
    assert undone.diagnostics["generated_exercise"] == first.diagnostics["generated_exercise"]
    assert last_exercise(session).tempo_bpm == 96 and last_exercise(session).id == first.diagnostics["generated_exercise_id"]
    assert "Undid" in undone.direct_answer and "96 BPM" in undone.direct_answer


def test_redo_restores_the_undone_revision(session):
    start(session)
    slower = ask(session, "Make it slower")
    ask(session, "Undo that")
    redone = ask(session, "Redo")
    assert redone.notation_abc == slower.notation_abc and tempo(redone) == 86 and "Redid" in redone.direct_answer


def test_undo_steps_back_through_several_versions_and_stops_at_the_first(session):
    start(session)
    for q in ("Make it slower", "Set it to 100 BPM", "make it faster"):
        ask(session, q)
    seen = []
    for _ in range(3):
        seen.append(tempo(ask(session, "Undo that")))
    assert seen == [100, 86, 96]
    again = ask(session, "Undo that")
    assert "Nothing to undo" in again.direct_answer and cs.working_tempo(session) == 96


def test_redo_with_nothing_to_redo_says_so(session):
    start(session)
    assert "Nothing to redo" in ask(session, "Redo").direct_answer


def test_a_new_revision_after_undo_drops_the_redo_branch(session):
    start(session)
    ask(session, "Make it slower")
    ask(session, "Undo that")
    ask(session, "Set it to 120 BPM")
    assert cs.history(session)["can_redo"] is False and "Nothing to redo" in ask(session, "Redo").direct_answer


def test_undo_also_undoes_an_engine_follow_up_not_only_tempo(session):
    first = start(session)
    harder = ask(session, "Make it harder")
    assert harder.diagnostics["generated_exercise_id"] != first.diagnostics["generated_exercise_id"]
    undone = ask(session, "Undo that")
    assert undone.diagnostics["generated_exercise"]["notes"] == first.diagnostics["generated_exercise"]["notes"]
    assert last_exercise(session).id == first.diagnostics["generated_exercise_id"]
    nxt = ask(session, "Make it easier")                       # the engines continue from the restored version
    assert nxt.diagnostics["parent_exercise_id"] == first.diagnostics["generated_exercise_id"]


def test_version_history_is_capped_at_ten(session):
    start(session)
    for bpm in range(60, 90, 2):
        ask(session, f"Set it to {bpm} BPM")
    assert cs.history(session)["versions"] == cs.MAX_VERSIONS
    undone = 0
    while "Nothing to undo" not in ask(session, "Undo that").direct_answer:
        undone += 1
    assert undone == cs.MAX_VERSIONS - 1


def test_the_same_request_twice_is_two_versions_only_when_something_changed(session):
    start(session)
    ask(session, "Set it to 100 BPM")
    n = cs.history(session)["versions"]
    ask(session, "Set it to 100 BPM")
    assert cs.history(session)["versions"] == n


# ---- no active exercise / unsupported ---------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["Make it slower", "Undo that", "Redo", "Set it to 100 BPM", "Add accents", "Explain why these notes work over the chords",
                               "Change the pattern to fourths", "Apply it to the chorus"])
def test_without_an_exercise_ami_explains_instead_of_inventing_one(session, q):
    resp = ask(session, q)
    assert resp is not None and "no exercise from this conversation" in resp.direct_answer.lower()
    assert not resp.notation_abc and not resp.diagnostics.get("generated_exercise_id")
    assert AMI_LAST_EXERCISE_KEY not in session


@pytest.mark.parametrize("q, word", [
    ("Change the pattern to fourths", "fourths"), ("Make it suitable for alto saxophone", "instrument"),
    ("Apply it to the chorus", "section"), ("Explain why these notes work over the chords", "notes fit"),
    ("Why did you choose those notes?", "notes fit"), ("Add accents and slurs", "slurs"),
])
def test_unsupported_revisions_get_an_honest_answer_and_leave_the_exercise_alone(session, q, word):
    first = start(session)
    before = dict(session[AMI_LAST_EXERCISE_KEY])
    resp = ask(session, q)
    assert "can't do that to your exercise yet" in resp.direct_answer and word in resp.direct_answer
    assert "unchanged" in resp.direct_answer and "undo that" in " ".join(resp.practice_steps)
    assert resp.diagnostics["exercise_revision_failed"] is True
    assert session[AMI_LAST_EXERCISE_KEY] == before and cs.history(session)["versions"] == 1
    assert last_exercise(session).id == first.diagnostics["generated_exercise_id"]


def test_bare_add_accents_means_downbeats_and_says_so(session):
    first = start(session)
    resp = ask(session, "Add accents")
    assert "accented the downbeats" in resp.direct_answer and resp.diagnostics.get("followup_kind") == "expression"
    assert any(resp.diagnostics["generated_exercise"]["accents"])
    assert resp.diagnostics["generated_exercise"]["notes"] == first.diagnostics["generated_exercise"]["notes"]


def test_a_new_unstructured_answer_ends_the_working_exercise(session):
    start(session)
    ask(session, "How should I practice the A section of this song?")      # not an exercise: the slot is unchanged, still revisable
    assert cs.current_version(session) is not None
    session.pop(AMI_LAST_EXERCISE_KEY)                                     # what the engines do when a non-exercise idea replaces it
    assert "no exercise from this conversation" in ask(session, "Make it slower").direct_answer.lower()


# ---- memory of the conversation ---------------------------------------------------------------------------------
def test_recent_turns_are_remembered_and_capped(session):
    start(session)
    for i in range(12):
        ask(session, f"Set it to {60 + i} BPM")
    turns = cs.history(session)["turns"]
    assert len(turns) == cs.MAX_TURNS and turns[-1]["q"] == "Set it to 71 BPM" and "BPM" in turns[-1]["a"]


def test_turn_text_is_short_and_carries_no_notation(session):
    start(session)
    for t in cs.history(session)["turns"]:
        assert len(t["q"]) <= 240 and len(t["a"]) <= 240 and "X:1" not in t["a"]


def test_the_target_conversation_keeps_one_exercise_through_every_step(session):
    first = start(session)
    ids = {first.diagnostics["generated_exercise_id"]}
    for q in ("Make it slower", "Set it to 100 BPM", "Add accents to the guide tones", "Undo that", "Redo"):
        resp = ask(session, q)
        assert resp.diagnostics.get("generated_exercise_id"), q
    assert cs.history(session)["versions"] >= 4
    assert last_exercise(session).context.concert_key == first.diagnostics["generated_exercise"]["context"]["concert_key"]
    assert session["practice_key"] == "Cm" and session["backing_bpm"] == 112


# ---- other app state is never written ---------------------------------------------------------------------------
def test_revisions_write_only_ami_conversation_keys(session):
    before = {k: v for k, v in session.items()}
    start(session)
    for q in ("Make it slower", "Undo that", "Redo", "Add accents", "Set it to 100 BPM"):
        ask(session, q)
    added = set(session) - set(before)
    assert added <= {AMI_LAST_EXERCISE_KEY, cs.STATE_KEY, "_ami_conv_owner", "_music_workflow_state_store"}   # the last one is the engines' own
    assert all(session[k] == v for k, v in before.items())
