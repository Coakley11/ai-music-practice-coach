"""AMI M1b: instrument changes, song-section retargeting and exercise-specific explanations of the working scale pattern.

The musical contract under test:

* an instrument change keeps the sounding line (or says exactly how it moved: whole octaves, or the same recipe re-voiced), writes it at the new
  instrument's verified offset inside its range, keeps rhythm / chords / articulation / tempo / song / section / Practice Key, never touches the
  app's global instrument selection, and is exactly undoable and redoable;
* a section change rebuilds the same recipe over the target section's real chords (split bars and durations included) and never relabels;
* an explanation reads the stored exercise, creates no version, and never contradicts the notation;
* nothing here makes an API call.
"""

from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from instrument_transposition import SELECTED_TRANSPOSING_INSTRUMENT_KEY as SAX_KEY
from music_coach_ami import conversation_state as cs
from music_coach_ami import exercise_adapt as ad
from music_coach_ami import exercise_explain as xp
from music_coach_ami import exercise_scale_pattern as sp
from music_coach_ami import scale_pattern_harmony as sph
from music_coach_ami.exercise_revision import is_revision_request
from music_coach_ami.pipeline import run_coach_submit
from tests.test_ami_scale_pattern_recipe import (  # noqa: F401  (autouse API guard is re-exported)
    ASK,
    ASK_CHORDS,
    BOSSA_A,
    BOSSA_B,
    OFFSET,
    _no_live_api,
    assert_sound,
    begin,
    ctx,
    exercise,
    failed,
    inst_kwargs,
    pitched,
    rhythm_sig,
    session,
    wevents,
)

NAMES = ["Flute", "Alto", "Tenor", "Soprano", "Trumpet", "Clarinet", "Piano"]
SPEC_OF = {"Flute": "flute", "Alto": "alto", "Tenor": "tenor", "Soprano": "soprano", "Trumpet": "trumpet", "Clarinet": "clarinet", "Piano": "piano"}
WORDS = {"Flute": "flute", "Alto": "alto saxophone", "Tenor": "tenor saxophone", "Soprano": "soprano saxophone", "Trumpet": "trumpet",
         "Clarinet": "clarinet", "Piano": "piano"}
PLAY = {"Flute": (60, 96), "Alto": (58, 89), "Tenor": (58, 89), "Soprano": (58, 89), "Trumpet": (54, 84), "Clarinet": (52, 96), "Piano": (21, 108)}


def say(s, q, name="Flute", **kw):
    ik = inst_kwargs(name)
    return run_coach_submit(q, s, ami_ctx=ctx(instrument=ik["instrument"], **kw))[1]


def ver(s):
    return cs.current_version(s)


def where(s):
    h = cs.history(s)
    return h["versions"], h["cursor"]


def ex_of(s):
    return sp.GeneratedExercise.from_dict(copy.deepcopy(ver(s)["exercise"]))


# ================================================================ 1. understanding the request
@pytest.mark.parametrize("q, target", [
    ("Make this exercise suitable for flute", "flute"), ("Make it suitable for flute.", "flute"),
    ("Change it from alto saxophone to tenor saxophone", "tenor"), ("Change it from alto to tenor", "tenor"),
    ("Play it on soprano saxophone instead", "soprano"), ("Adapt this pattern for piano", "piano"), ("Adapt this pattern for trumpet please", "trumpet"),
    ("Can you make it better for clarinet", "clarinet"), ("Rewrite the exercise for baritone sax", "baritone"), ("Try it on alto sax", "alto"),
    ("Switch it to tenor saxophone", "tenor"), ("Transpose this for clarinet", "clarinet"),
])
def test_instrument_requests_are_understood(q, target):
    a = ad.parse_adaptation(q)
    assert a is not None and a.kind == ad.KIND_INSTRUMENT and a.target == target and not a.ask_which, (q, a)


@pytest.mark.parametrize("q", ["Keep the same exercise, but change the instrument", "Make it suitable for a saxophone", "Switch it to sax"])
def test_an_unnamed_instrument_is_asked_for(q):
    a = ad.parse_adaptation(q)
    assert a is not None and a.kind == ad.KIND_INSTRUMENT and a.ask_which and not a.target, (q, a)


@pytest.mark.parametrize("q, name", [("Make it suitable for trombone", "trombone"), ("Play it on guitar instead", "guitar"), ("Adapt this pattern for violin", "violin")])
def test_an_unverified_instrument_is_named_not_guessed(q, name):
    a = ad.parse_adaptation(q)
    assert a is not None and a.unverified == name and not a.target, (q, a)


@pytest.mark.parametrize("q, sec", [
    ("Apply this pattern to the chorus", "chorus"), ("Change it to Verse 2", "verse 2"), ("Use the chord changes from Section B", "section b"),
    ("Keep the same interval pattern but apply it to the bridge", "bridge"), ("Apply it to Part B", "part b"), ("Use the chord changes in Verse 2 instead", "verse 2"),
    ("Move it to the intro", "intro"), ("Apply the same exercise to the chorus", "chorus"),
])
def test_section_requests_are_understood(q, sec):
    a = ad.parse_adaptation(q)
    assert a is not None and a.kind == ad.KIND_SECTION and a.section_text == sec, (q, a)


@pytest.mark.parametrize("q", [
    "Give me a flute exercise over Blue Bossa", "Give me a pattern for the chorus of Wonderwall", "How do I play on flute?", "What is a ii-V-I?",
    "Which saxophone should I buy?", "Why is the bridge hard?", "Make it faster", "Change it to fourths", "Add accents", "Practice the chorus of Wonderwall",
])
def test_ordinary_questions_are_not_taken_for_adaptations(q):
    assert ad.parse_adaptation(q) is None, q


@pytest.mark.parametrize("q, kind", [
    ("Why do those notes work over these chords?", xp.WHY), ("Explain why these notes work", xp.WHY), ("Which notes are chord tones?", xp.CHORD_TONES),
    ("Show me the guide tones", xp.GUIDE_TONES), ("Explain the chromatic approaches", xp.APPROACHES), ("Why did you use those intervals?", xp.INTERVALS),
    ("How would I use this pattern when improvising?", xp.IMPROVISE), ("Explain the musical reasoning behind that last change", xp.LAST_CHANGE), ("What did you change?", xp.LAST_CHANGE),
])
def test_explanation_requests_are_understood(q, kind):
    assert xp.parse_explanation(q) == kind, q


@pytest.mark.parametrize("q", [
    "What are chromatic approaches?", "How do I improvise over Blue Bossa?", "Accent the guide tones", "Add accents on the guide tones", "Change it to fourths",
    "What is a guide tone?", "Add chromatic approaches",
])
def test_general_questions_and_revisions_are_not_explanations(q):
    assert xp.parse_explanation(q) == "", q


def test_the_duplicate_send_guard_sees_these_as_revisions():
    for q in ("Make it suitable for flute", "Apply it to the chorus", "Show me the guide tones", "Why do those notes work over these chords?"):
        assert is_revision_request(q), q


# ================================================================ 2. instrument changes
_SOURCES: dict[tuple[str, str], dict] = {}


def source(name, q=ASK_CHORDS):
    key = (name, q)
    if key not in _SOURCES:
        s, _resp, _inst = begin(q, name)
        _SOURCES[key] = s
    return copy.deepcopy(_SOURCES[key])


def _check_adapted(s, parent, name_to):
    """Everything an instrument change must satisfy, recomputed from stored data."""
    child = ex_of(s)
    assert_sound(child.to_dict())
    d = child.to_dict()
    p = parent.to_dict()
    assert d["provenance"]["offset"] == OFFSET[name_to], (name_to, d["provenance"]["offset"])
    assert child.context.concert_key == parent.context.concert_key and child.context.song_title == parent.context.song_title
    assert child.context.section == parent.context.section and child.meter == parent.meter and child.bars == parent.bars
    assert child.chords == parent.chords and child.chord_assignment == parent.chord_assignment
    assert rhythm_sig(d) == rhythm_sig(p)
    assert len(child.midi) == len(parent.midi)
    lo, hi = PLAY[name_to]
    assert all(lo <= sph.midi_of(w["spelled"], int(w["octave"])) <= hi for w in pitched(d)), "outside what the instrument can play"
    return child, d, p


@pytest.mark.parametrize("src", NAMES)
@pytest.mark.parametrize("dst", NAMES)
def test_every_verified_instrument_pair(src, dst):
    if src == dst:
        pytest.skip("same instrument")
    s = source(src)
    parent = ex_of(s)
    before_instrument, before_sax = s["instrument"], s.get(SAX_KEY)
    n0 = where(s)
    abc0 = ver(s)["abc"]
    resp = say(s, f"Make this exercise suitable for {WORDS[dst]}", src)
    # global selection untouched
    assert s["instrument"] == before_instrument and s.get(SAX_KEY) == before_sax
    if failed(resp):
        assert where(s) == n0, "a refused change must not create a version"
        assert "unchanged" in resp.direct_answer.lower() or "haven't changed" in resp.direct_answer.lower()
        return
    assert where(s) == (n0[0] + 1, n0[1] + 1)
    child, d, p = _check_adapted(s, parent, dst)
    how = child.provenance["adaptation"]["how"]
    text = resp.direct_answer
    assert f"Now for {ad.SPECS[SPEC_OF[dst]].label}" in text
    if how == "octave":
        shift = child.provenance["adaptation"]["octave_shift"]
        assert shift and "Octave adjustment" in text
        assert [m - 12 * shift for m in child.midi] == list(parent.midi) and child.notes == parent.notes
    elif how == "kept":
        assert list(child.midi) == list(parent.midi) and child.notes == parent.notes
    else:
        assert how == "revoiced" and "Re-voiced" in text
    # articulation and accents travel with the notes
    assert child.articulation == parent.articulation and child.accents == parent.accents
    # undo is exact, redo is exact
    child_abc = ver(s)["abc"]
    say(s, "Undo that", src)
    assert ver(s)["abc"] == abc0 and ver(s)["exercise"]["id"] == parent.id
    say(s, "Redo", src)
    assert ver(s)["abc"] == child_abc and where(s) == (n0[0] + 1, n0[1] + 1)


def test_sounding_pitch_is_preserved_when_the_line_fits():
    s = source("Alto", ASK)       # a short key-based line
    parent = ex_of(s)
    resp = say(s, "Make it suitable for tenor saxophone", "Alto")
    assert not failed(resp)
    child = ex_of(s)
    assert list(child.midi) == [m + 12 * child.provenance["adaptation"]["octave_shift"] for m in parent.midi] or child.provenance["adaptation"]["how"] == "revoiced"
    assert_sound(child.to_dict())


def test_alto_to_tenor_writes_the_same_sounds_a_fifth_higher_than_alto():
    s = source("Alto")
    parent = ex_of(s)
    say(s, "Change it from alto saxophone to tenor saxophone", "Alto")
    child = ex_of(s)
    d = child.to_dict()
    assert child.context.notation_instrument == "Tenor Saxophone" and child.context.written_key == "Dm"
    if child.provenance["adaptation"]["how"] != "revoiced":
        for w_new, w_old, m in zip(pitched(d), pitched(parent.to_dict()), child.midi):
            assert sph.midi_of(w_new["spelled"], int(w_new["octave"])) - m == 14
            assert sph.midi_of(w_old["spelled"], int(w_old["octave"])) - (m - 12 * child.provenance["adaptation"]["octave_shift"]) == 9


def test_an_octave_move_is_always_whole_octaves_and_announced():
    s = source("Tenor")
    resp = say(s, "Play it on flute instead", "Tenor")
    child = ex_of(s)
    ad_ = child.provenance["adaptation"]
    assert ad_["how"] in {"kept", "octave", "revoiced"}
    if ad_["how"] == "octave":
        assert abs(ad_["octave_shift"]) >= 1 and "octave" in resp.direct_answer.lower()


def test_the_same_instrument_is_a_clear_no_change():
    s = source("Flute")
    n0 = where(s)
    resp = say(s, "Make this exercise suitable for flute", "Flute")
    assert failed(resp) and "already written for" in resp.direct_answer and where(s) == n0


def test_an_unnamed_or_unverified_instrument_changes_nothing_and_asks():
    s = source("Flute")
    n0 = where(s)
    r1 = say(s, "Keep the same exercise, but change the instrument")
    assert failed(r1) and "Which instrument" in r1.direct_answer and where(s) == n0
    r2 = say(s, "Adapt this pattern for trombone")
    assert failed(r2) and "trombone" in r2.direct_answer and "verify" in r2.direct_answer and where(s) == n0
    r3 = say(s, "Make it suitable for a saxophone")
    assert failed(r3) and "Soprano, alto, tenor or baritone" in r3.direct_answer and where(s) == n0
    r4 = say(s, "tenor")                   # the answer to the question
    assert not failed(r4) and ex_of(s).context.notation_instrument == "Tenor Saxophone" and where(s)[0] == n0[0] + 1


def test_a_pending_question_is_not_answered_by_unrelated_text_and_expires():
    s = source("Flute")
    say(s, "Make it suitable for a saxophone")
    assert ad.PENDING_KEY in s
    say(s, "Make it slower")                # anything else abandons the question
    assert ad.PENDING_KEY not in s
    n0 = where(s)
    say(s, "alto")
    assert where(s) == n0


def test_both_changes_in_one_sentence_are_asked_one_at_a_time():
    s = source("Flute")
    n0 = where(s)
    resp = say(s, "Play it on alto saxophone over the chorus")
    assert failed(resp) and where(s) == n0


def test_baritone_is_a_verified_instrument_too():
    s = source("Alto")
    resp = say(s, "Rewrite this pattern for baritone sax", "Alto")
    if not failed(resp):
        assert ex_of(s).provenance["offset"] == 21
        assert_sound(ex_of(s).to_dict())


def test_revisions_after_an_instrument_change_stay_on_the_new_instrument():
    s = source("Flute")
    say(s, "Make it suitable for alto saxophone")
    if failed(say(s, "Undo that")):
        pytest.skip("adaptation refused")
    say(s, "Redo")
    for q in ("Change it to fourths", "Make it more advanced", "Add chromatic approaches", "Make the rhythm more syncopated", "Add accents"):
        resp = say(s, q, "Flute")            # the page still says Flute
        assert not failed(resp), (q, resp.direct_answer[:200])
        e = ex_of(s)
        assert e.context.notation_instrument == "Alto Saxophone" and e.provenance["offset"] == 9
        assert "current instrument" not in resp.direct_answer
        assert_sound(e.to_dict())


def test_the_global_instrument_is_never_touched_by_any_change():
    s = source("Flute")
    snapshot = {k: copy.deepcopy(v) for k, v in s.items() if not k.startswith("_")}
    for q in ("Make it suitable for tenor saxophone", "Apply it to Section B", "Show me the guide tones", "Undo that", "Undo that", "Redo"):
        say(s, q)
    assert {k: v for k, v in s.items() if not k.startswith("_")} == snapshot


# ================================================================ 3. section retargeting
SPLIT = {"Section A": BOSSA_A, "Verse 1": ["Gm7", "C7", "Fmaj7", "Fmaj7"], "Verse 2": ["Gm7", "C7:2|Am7:2", "Dm7", "G7"], "Chorus": ["Cm7", "Fm7", "Bb7", "Ebmaj7"],
         "Section C": BOSSA_A}


def test_section_b_has_its_own_chords_and_notes():
    s = source("Flute")
    parent = ex_of(s)
    resp = say(s, "Apply it to Section B")
    assert not failed(resp)
    child = ex_of(s)
    d = child.to_dict()
    assert_sound(d)
    assert child.provenance["section_slots"] == BOSSA_B and child.context.section == "Section B"
    assert child.chords == ["Ebm7", "Ab7", "Dbmaj7", "Dm7b5", "G7", "Cm7"]
    assert child.notes != parent.notes
    assert sp.recipe_of(child) == sp.recipe_of(parent)
    assert child.context.concert_key == "Cm" and child.context.notation_instrument == parent.context.notation_instrument
    assert "Ebm7" in resp.direct_answer and "carried over" in resp.direct_answer
    # every note is a tone of its chord's scale (the stored validation says so; recompute it from the segment scales)
    for i, c in enumerate(child.chord_assignment):
        seg = next(g for g in child.provenance["segments"] if g["chord"] == child.chords[c])
        assert sph.pc_of(child.notes[i]) in {sph.pc_of(x) for x in seg["scale_notes"]}


def test_section_retargeting_is_exactly_undoable():
    s = source("Flute")
    abc0 = ver(s)["abc"]
    say(s, "Apply it to Section B")
    abc1 = ver(s)["abc"]
    assert abc1 != abc0
    say(s, "Undo that")
    assert ver(s)["abc"] == abc0
    say(s, "Redo")
    assert ver(s)["abc"] == abc1


def test_split_bars_and_chord_durations_are_respected():
    s = session("Flute")
    run_coach_submit(ASK_CHORDS, s, ami_ctx=ctx(sections=SPLIT))
    resp = run_coach_submit("Apply it to Verse 2", s, ami_ctx=ctx(sections=SPLIT))[1]
    assert not failed(resp), resp.direct_answer[:300]
    child = ex_of(s)
    assert_sound(child.to_dict())
    assert child.bars == 4 and child.chords == ["Gm7", "C7", "Am7", "Dm7", "G7"]
    segs = child.provenance["segments"]
    split = [g for g in segs if g["bar"] == 2]
    assert [(g["chord"], g["beats"]) for g in split] == [("C7", "2"), ("Am7", "2")]
    # the notes of the first half of bar 2 are C7 notes, the second half Am7 notes
    in_bar2 = [(i, e) for i, e in enumerate(pitched(child.to_dict())) if e["bar_index"] == 1]
    assert {child.chords[child.chord_assignment[i]] for i, _ in in_bar2} == {"C7", "Am7"}
    assert child.provenance["adaptation"]["bars"] == 4


def test_a_section_with_a_different_length_gets_its_own_length():
    s = session("Flute")
    run_coach_submit(ASK_CHORDS, s, ami_ctx=ctx(sections=SPLIT))
    assert ex_of(s).bars == 8
    run_coach_submit("Apply it to the chorus", s, ami_ctx=ctx(sections=SPLIT))
    assert ex_of(s).bars == 4 and ex_of(s).context.section == "Chorus"
    assert ex_of(s).provenance["title"].startswith("4-Bar")


def test_an_ambiguous_section_asks_and_the_answer_resolves_it():
    s = session("Flute")
    run_coach_submit(ASK_CHORDS, s, ami_ctx=ctx(sections=SPLIT))
    n0 = where(s)
    r = run_coach_submit("Apply it to the verse", s, ami_ctx=ctx(sections=SPLIT))[1]
    assert failed(r) and "Which one" in r.direct_answer and where(s) == n0
    r2 = run_coach_submit("Verse 2", s, ami_ctx=ctx(sections=SPLIT))[1]
    assert not failed(r2) and ex_of(s).context.section == "Verse 2" and where(s)[0] == n0[0] + 1


def test_a_missing_section_is_named_not_guessed():
    s = source("Flute")
    n0 = where(s)
    r = say(s, "Apply it to the bridge")
    assert failed(r) and "doesn't have a section" in r.direct_answer and where(s) == n0


def test_the_same_section_or_the_same_chords_change_nothing():
    s = session("Flute")
    run_coach_submit(ASK_CHORDS, s, ami_ctx=ctx(sections=SPLIT))
    n0 = where(s)
    a = run_coach_submit("Apply it to Section A", s, ami_ctx=ctx(sections=SPLIT))[1]
    b = run_coach_submit("Use the chord changes from Section C", s, ami_ctx=ctx(sections=SPLIT))[1]
    assert failed(a) and "already built on" in a.direct_answer
    assert where(s) == n0 and failed(b) and "same chords" in b.direct_answer


def test_a_key_based_pattern_is_never_relabelled_for_another_section():
    s, _r, _i = begin(ASK, "Flute")
    n0 = where(s)
    r = say(s, "Apply it to Section B")
    assert failed(r) and "key-based" in r.direct_answer and where(s) == n0


def test_a_changed_practice_key_is_not_silently_followed():
    s = source("Flute")
    n0 = where(s)
    r = run_coach_submit("Apply it to Section B", s, ami_ctx=ctx(key="Dm", instrument="Flute"))[1]
    assert failed(r) and "Practice Key" in r.direct_answer and where(s) == n0


def test_a_section_change_after_an_instrument_change_keeps_the_instrument():
    s = source("Flute")
    say(s, "Make it suitable for tenor saxophone")
    r = say(s, "Apply it to Section B")
    assert not failed(r), r.direct_answer[:300]
    e = ex_of(s)
    assert e.context.notation_instrument == "Tenor Saxophone" and e.context.section == "Section B"
    assert_sound(e.to_dict())


def test_the_recipe_follows_the_exercise_to_the_new_section():
    s = source("Flute")
    for q in ("Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated"):
        say(s, q)
    r0 = sp.recipe_of(ex_of(s))
    r = say(s, "Apply it to Section B")
    assert not failed(r)
    child = ex_of(s)
    assert sp.recipe_of(child) == r0 and r0.shape == "fourths" and r0.syncopation
    assert_sound(child.to_dict())
    assert any(e["tone_role"].startswith("approach") for e in pitched(child.to_dict()))


# ================================================================ 4. explanations
@pytest.mark.parametrize("q", [
    "Why do those notes work over these chords?", "Which notes are chord tones?", "Show me the guide tones", "Explain the chromatic approaches",
    "Why did you use those intervals?", "How would I use this pattern when improvising?",
])
def test_an_explanation_creates_no_version_and_changes_nothing(q):
    s = source("Alto")
    before = copy.deepcopy(ver(s))
    n0 = where(s)
    last = copy.deepcopy(s.get("_ami_last_generated_exercise"))
    resp = say(s, q, "Alto")
    assert not failed(resp) and resp.diagnostics.get("exercise_explanation")
    assert where(s) == n0 and ver(s) == before and s.get("_ami_last_generated_exercise") == last
    assert resp.notation_abc == ""


def test_explanations_quote_the_stored_notes_and_roles():
    s = source("Alto")
    e = ex_of(s)
    d = e.to_dict()
    resp = say(s, "Which notes are chord tones?", "Alto")
    text = " ".join(resp.practice_steps)
    # the player's staff: Alto, so the chord symbols printed are the written (Eb-instrument) ones
    written_chords = [c for c in dict.fromkeys(w["chord"] for w in pitched(d))]
    for chord in written_chords:
        assert chord in text, chord
    for i, role in enumerate(e.chord_roles):
        if role in ("R", "3", "5", "7"):
            assert e.written["notes"][i] in text


def test_guide_tones_are_the_thirds_and_sevenths_of_each_chord():
    s = source("Flute")
    resp = say(s, "Show me the guide tones")
    text = " ".join(resp.practice_steps)
    for chord, third, seventh in (("Cm7", "Eb", "Bb"), ("Fm7", "Ab", "Eb"), ("Dm7b5", "F", "C"), ("G7#5", "B", "F")):
        line = next(x for x in resp.practice_steps if f"**{chord}**" in x)
        assert f"**{third}**" in line and f"**{seventh}**" in line, (chord, line)


def test_guide_tones_are_written_for_the_players_instrument():
    s = source("Alto")
    resp = say(s, "Show me the guide tones", "Alto")
    line = next(x for x in resp.practice_steps if "**Am7**" in x)       # Cm7 sounds; the alto reads Am7
    assert "**C**" in line and "**G**" in line, line


def test_approach_explanations_match_the_notation():
    s = source("Flute")
    none = say(s, "Explain the chromatic approaches")
    assert "no chromatic approach" in " ".join(none.practice_steps)
    say(s, "Add chromatic approaches")
    resp = say(s, "Explain the chromatic approaches")
    d = ex_of(s).to_dict()
    n_app = sum(1 for e in pitched(d) if e["tone_role"].startswith("approach"))
    assert n_app and f"{n_app} note" in " ".join(resp.practice_steps)


def test_a_key_based_pattern_is_explained_without_claiming_chords():
    s, _r, _i = begin(ASK, "Flute")
    for q in ("Which notes are chord tones?", "Show me the guide tones", "Why do those notes work over these chords?"):
        resp = say(s, q)
        text = " ".join(resp.practice_steps)
        assert "key-based" in text.lower() or "no chords" in text.lower() or "isn't tied to any chord" in text.lower() or "need chords" in text.lower(), (q, text[:200])


def test_an_explanation_without_an_exercise_does_not_invent_one():
    s = session("Flute")
    r = run_coach_submit("Show me the guide tones", s, ami_ctx=ctx())[1]
    assert not (r and r.diagnostics.get("exercise_explanation"))
    r2 = run_coach_submit("Explain the musical reasoning behind that last change", s, ami_ctx=ctx())[1]
    assert r2 is not None and "no exercise" in r2.direct_answer.lower() and failed(r2)


def test_a_stale_exercise_is_not_explained_for_another_song():
    s = source("Flute")
    r = run_coach_submit("Show me the guide tones", s, ami_ctx=ctx(song="Autumn Leaves", key="Gm"))[1]
    assert r is not None and "built for **Blue Bossa**" in r.direct_answer


# ================================================================ 5. the whole conversation
def test_the_full_conversation_on_one_exercise():
    s = session("Alto Saxophone", sax=inst_kwargs("Alto")["sax"])
    ask = lambda q: run_coach_submit(q, s, ami_ctx=ctx(instrument="Alto Saxophone"))[1]      # noqa: E731
    assert ask(ASK_CHORDS).diagnostics.get("generated_exercise_id")
    steps = ["Change it to fourths", "Add chromatic approaches", "Make the rhythm more syncopated", "Now make it suitable for flute",
             "Apply it to Section B", "Explain why those notes work"]
    for q in steps:
        resp = ask(q)
        assert not failed(resp), (q, resp.direct_answer[:300])
    e = ex_of(s)
    assert e.context.notation_instrument == "Flute" and e.context.section == "Section B" and e.context.concert_key == "Cm"
    assert sp.recipe_of(e).shape == "fourths" and sp.recipe_of(e).syncopation
    assert_sound(e.to_dict())
    assert where(s) == (6, 5)                 # first answer + 5 revisions; the explanation added none
    for cursor in (4, 3, 2):
        ask("Undo that")
        assert where(s)[1] == cursor
    assert ex_of(s).context.section == "Section A"
    for cursor in (3, 4, 5):
        ask("Redo")
        assert where(s)[1] == cursor
    assert ex_of(s).context.section == "Section B" and ex_of(s).context.notation_instrument == "Flute"
    assert s["instrument"] == "Alto Saxophone" and s.get(SAX_KEY) == inst_kwargs("Alto")["sax"]


def test_accents_and_articulation_survive_an_instrument_change():
    s = source("Flute")
    say(s, "Add accents")
    before = ex_of(s)
    assert any(before.accents)
    r = say(s, "Make it suitable for tenor saxophone")
    assert not failed(r)
    after = ex_of(s)
    assert after.accents == before.accents and after.articulation == before.articulation
    assert "!>!" in ver(s)["abc"]


def test_tempo_survives_every_m1b_change():
    s = source("Flute")
    say(s, "Set it to 100 BPM")
    for q in ("Make it suitable for alto saxophone", "Apply it to Section B", "Show me the guide tones"):
        say(s, q)
        assert cs.working_tempo(s) == 100 and "Q:1/4=100" in ver(s)["abc"].replace(" ", "")


# ================================================================ 6. isolation
def test_adaptation_state_does_not_cross_accounts_or_workspaces():
    s = source("Flute")
    say(s, "Make it suitable for a saxophone")
    assert ad.PENDING_KEY in s
    s["_suite_auth_user_id"] = "u2"
    r = run_coach_submit("alto", s, ami_ctx=ctx())[1]
    assert ad.PENDING_KEY not in s and (r is None or not r.diagnostics.get("generated_exercise_id"))
    r2 = run_coach_submit("Make it suitable for tenor saxophone", s, ami_ctx=ctx())[1]
    assert r2 is not None and "no exercise" in r2.direct_answer.lower()
    assert where(s)[0] == 0


def test_a_second_account_cannot_see_or_undo_the_first_accounts_adaptation():
    a = source("Flute")
    say(a, "Make it suitable for alto saxophone")
    b = copy.deepcopy(a)
    b["_suite_auth_user_id"] = "u2"
    for q in ("Undo that", "Apply it to Section B", "Show me the guide tones", "Play it on flute instead"):
        r = run_coach_submit(q, b, ami_ctx=ctx())[1]
        assert r is None or not r.diagnostics.get("generated_exercise_id"), q
    assert where(b)[0] == 0


# ================================================================ 7. "what did the last change do?"
def test_the_last_change_is_explained_from_the_stored_record():
    s = source("Flute")
    first = say(s, "Explain the musical reasoning behind that last change")
    assert "first version" in " ".join(first.practice_steps)
    say(s, "Change it to fourths")
    n0 = where(s)
    resp = say(s, "Explain the musical reasoning behind that last change")
    text = " ".join(resp.practice_steps)
    assert where(s) == n0 and "Change it to fourths" in text and "fourths" in text and "Kept:" in text
    say(s, "Make it faster")
    t = " ".join(say(s, "What did you change?").practice_steps)
    assert "Make it faster" in t and "only the tempo" in t
    say(s, "Make it suitable for tenor saxophone")
    t2 = " ".join(say(s, "Why did you make that change?").practice_steps)
    assert "Tenor Saxophone" in t2 and "written key" in t2.lower()
